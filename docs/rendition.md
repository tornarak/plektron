# Typeface in the stores: a design, waiting on the editor

The stores record what a page says and not how it is set. This file is the
design for recording how it is set, as a run of a typeface inside a line. It
is a design and nothing is built. What the editor rules goes into
`keying_spec.md`, which binds the reading passes; this file keeps the reasoning.
The counts below were taken on 2026-11-16, and each says how, since nothing
regenerates them.

## The gap

**Ground truth carries no typeface.** All 30,040 lines in *The Chukchee*'s
`gt/ocr/` (719 pages) are a single plain ALTO `String`, and none has a style.
Each feature the print sets in another face was handled on its own, by
flattening it into characters or by dropping it:

- **Footnote marks** are keyed as Unicode superscripts (`keying_spec.md` §2.10).
  This is a character for a setting, and it works because a raised digit has a
  codepoint.
- **Run-in heads** are keyed as ASCII capitals where the print sets small capitals,
  and in title case where it sets italic (§2.13). The face survives only because
  the head's depth implies it.
- **Italics in the body** (binomials, titles, foreign words) were never recorded.
  They are not in *The Chukchee*'s ground truth.
- **Collation** may add `<hi rend="smallcaps">` "where the emphasis is evidently
  deliberate" (`.claude/agents/collator.md`). That is a model's markup in the
  TEI, never ratified against the scan.

The 1900 *Materials* set emphasis by **letterspacing** (разрядка), which no
character can stand for. The reading pass keys it unspaced, with a `layout` note
(`.claude/skills/read-materials-page/`). The note tells a human; it tells no rule
which words were spaced.

### What each book sets, and how often

**No source records a face, so every count comes off the scans.** The PDFs were
checked with PyMuPDF:

- *The Chukchee*'s text layer is all Courier, with no italic or bold flag on any
  span. Its superscript flag falls on ordinary words whose baselines wobble.
- The *Materials*' two copies are `GlyphLessFont`, with no flags.
- Letterspacing leaves no trace in the layer: 0 of 103,902 lowercase words of four
  or more letters are wider than 1.45× their line's median, and the running head
  of `1-022`, set spaced, comes out plain.
- `ocr import` keeps only each span's text and origin
  (`harness/textlayer.py:108–119`), so it would drop font data anyway.

**A sample read off the scans.** Ten pages a book, read by a model and not
ratified. *The Chukchee*'s were every 72nd of its 717 non-exempt pages, from
the 36th. The *Materials*' were every 90th of its 451, from the 45th, plus five
chosen for layout: the trial pages, the introduction, a parallel-column page and
a *Примѣчанія* page. Every run, with its line, is in `docs/rendition-sample.md`;
the tallies are here.

| | *The Chukchee* | *Materials* |
|---|---|---|
| pages; lines | 1-066 1-154 1-250 1-350 2-066 2-140 2-214 3-022 3-094 3-166; 429 | 1-021 1-022 1-023 1-064 1-154 1-178 1-200 1-246 1-336 1-426; 372 |
| italic | 15: 10 figure letters (1-154 ×8), 4 run-in heads, 1 binomial (*Salmo sanguinolentus*, 1-250) | 10, all the note openers' «(стр. N)» ("p. N") |
| small capitals | 9: 6 run-in heads, 3 plate numerals | 0 inside a line; the running heads are set in small capitals whole |
| letterspaced | 0 | 35: 14 in running text (in the introduction, surnames, and twice the word "Imperial"), 13 titles and «Примѣчанія къ № N» heads, 8 running heads |
| bold | 0 (heavier inking on 3-166 is the same letterforms) | 5, all section numbers («19.») |
| a smaller face for a whole block | footnotes, a block quotation | 27 blocks: every note, footnote and «Записано отъ…» line. 26 Chukchi words inside them are set in the wider body face |
| superscripts | 45: 34 footnote marks, 6 figure-letter numbers (`a³`), 5 of the glyph `ᵋ`, all keyed as characters | 9, all footnote marks in the text; every note opener sits on the baseline |

Three things follow from it:

- **A face that covers a whole block belongs to the block, not to a run.** A
  footnote's smaller face, a title spaced as a whole line, a running head:
  these follow from the zone the block is keyed in, and marking them would state
  the zone twice. What needs markup is a face that *changes within* a line or a
  block: a surname spaced in a sentence, a binomial in italic, «(стр. N)» in
  italic at a note's head.
- **Much of it is predictable, and is recorded anyway.** The *Materials*'
  italic «(стр. N)» and bold section numbers fall where a rule would put them.
  They are keyed as printed, because a rule that predicted them would be a second
  reading of the same fact, and recording is cheap.
- **Every superscript in the sample is already a character.** Nothing calls for
  superscript as a face.

**What readers already noted.** *The Chukchee*'s 718 proposals mention italic in
145 notes on 112 pages, and small capitals (as a face, not the notation's letters)
in about 180 on 149. Superscripts appear in 1,131 notes, nearly all of them
footnote marks. These are mentions a reader chose to make, a floor and not a
census.

## The proposal

Three layers, each holding one fact once.

### 1. The store: ALTO's own typeface

- **A line is one `String` per run of one face.** Each run carries `STYLEREFS` to
  a `<TextStyle FONTSTYLE="…">`, from ALTO's closed list: bold, italics,
  subscript, superscript, smallcaps, underline.
- **Letterspacing, which ALTO lacks, is a tag:** `TAGREFS` to an
  `<OtherTag TYPE="rendition" LABEL="spaced">`. kraken's `parse_alto_langs`
  (`kraken/lib/xml/alto.py:61–78`) reads only tags of type `language`, and only on
  regions and lines, so the tag cannot be taken for a language.
- **The line's text is its Strings joined, as kraken joins them.** kraken 7.0.3
  concatenates `CONTENT` with no separator and reads each `<SP>` as a space
  (`alto.py:223–225`). So spaces inside a run stay in its `CONTENT`, as now. A
  run's `CONTENT` never begins or ends with a space, because a word boundary at a
  run's edge is an explicit `<SP/>`. An empty `String` is never written, since
  kraken reads one as a space.
- **The harness takes kraken's join.** `lines._line_text`
  (`harness/lines.py:350`) joins Strings with a space and ignores `<SP>`, so the
  harness and training would read a split line two ways. Changing it is a no-op
  today: every line is one String, and no store holds an `<SP>`.

So typeface is extra structure on the text, never characters in it. OCR training,
the detectors, the lexicon and search read the same line text as before.

The rejected alternative is markup inside `CONTENT` (`{i:Canis lupus}`). It is
simpler to write, but every reader of a line would then meet markup as
characters, and ketos would train on it.

### 2. The notation: where text is typed

People and models type a line, so the face needs a spelling in the places a
line is typed: `proposal.json`, `decision.json` and the review editor's text box.
That spelling is `⟦i:Canis lupus⟧`, a run between `⟦ ⟧` opening with its face's
name.

- **It lives in `review/` only.** Restore parses it into runs for `gt/ocr/`, and
  the editor renders a page's runs back into it. Each store has one encoding of a
  fact.
- **The delimiters were chosen by census.** `⟦ ⟧ ⟨ ⟩ ‹ › ⌜ ⌝` occur nowhere: not
  in either book's `gt/ocr/` or `mz/ocr/`, any proposal or decision, or anything
  under `jesup/edition/`. Every likelier character is taken:
  - `[ ]` are printed;
  - `{` `}` `|` `*` `` ` `` `_` are JSON or Markdown syntax in `edition/`, and
    OCR noise in `mz/ocr/`;
  - `^ ~ _ +` are keying shorthand (`config/handle.json`);
  - `< >` are XML.

### 3. A closed set of faces per text

Each text declares the faces it prints, read whole through `layout.shared`
(the text's set, else its workspace's), as `config/keyboard.json` is, and not key
by key as `config/keying.json` is.

- On the sample's evidence, *The Chukchee* declares `i` (italics) and `sc`
  (smallcaps), and the *Materials* declare `sp` (spaced), `i` and `b` (bold). A
  text's own layer is a full set, not additions to its workspace's: the
  *Materials* set small capitals only in whole running heads, which are the zone's
  (above), so a run of `sc` there would be a slip to refuse.
- `proposal check` and restore refuse a face the text does not declare.
- `tei generate` writes each run as `<hi rend="…">`.
- **Superscript is in no set.** Footnote marks stay characters, as §2.10 and the
  *Materials* ruling of 2026-11-16 key them, so one fact never has two encodings.
  In the sample, every superscript (54 across both books) is one a character
  already covers. Notation glyphs such as `ᵋ` are letters, not a face.

## Provenance

A face is read off the scan, so it is a reading, with a rank, ratified as text
is.

The question is the *Materials*' prose. Under `prose_stands` a Russian line
reaches ground truth on the model's reading. Should a face the model marked in
that line stand with it? **Recommended: no. Every styled run comes to the
editor.** Runs are few, and a face can be checked on the scan without reading
Russian. Mechanically, a proposal line carrying `⟦` does not stand.
`detectors.prose_only` looks at letters only and would let one through, so
`review.standing` needs the explicit test.

## Migration

Every site that reads or writes a line's text, from the code audit:

| site | today | change |
|---|---|---|
| `lines._line_text` (`lines.py:350`), behind `page_lines` and its ~30 callers | joins Strings with `" "`, ignores `<SP>` | kraken's join |
| `corrections.load_lines` (`corrections.py:105`) | first `String` only | read through `_line_text` |
| restore (`review.py:738–740`) | refuses a line without exactly one `String` | parse the notation into runs |
| `corrections.build_fragment` (`corrections.py:152`) | one `String` | runs, as restore writes them: each line's text goes to the store it came from |
| `normalize` quote and apostrophe traps (`normalize.py:479`, `:528`) | per `String`, so a token across a run edge is missed | read lines |
| `normalize` footnote check (`normalize.py:571`) | joins with `" "` | read lines |
| captions (`figures.py:3112`, `:3130`) | one `String` per *printed line* | group by `TextLine` before joining |
| `recognize.assemble` (`recognize.py:871`) | counts characters through the space join | follows `_line_text` |
| `ocr predict` (`recognize.py:458–471`), `ocr import` (`textlayer.py:410`) | one `String` | unchanged: no machine source knows a face |
| `corpus mets`, the ketos lists | copy the file | unchanged |

The order keeps the corpus valid at each step:

1. `_line_text` takes kraken's join, a no-op today.
2. `corrections.load_lines` reads through it.
3. normalize reads lines, not Strings.
4. Captions group by `TextLine`.
5. Restore and `build_fragment` write runs, and `proposal check` learns the
   notation.
6. The review editor renders and accepts it.
7. `tei generate` emits `<hi>`.

Only human-ratified writers ever emit runs.

## Later, and optional

A retro pass could add body italics and small capitals across *The Chukchee*'s
719 pages: a model proposes runs against the scan, and the editor ratifies them.
The §2.13 heads would be re-keyed only in such a pass.

## Waits on the editor

- The delimiter spelling, `⟦i:…⟧`, and the faces' short names.
- **The *Materials*' Chukchi words inside the notes, set in the body face** while
  the note around them is in the smaller one (26 in the sample). Either this is a
  face, `body`, keyed as a run, or it is left implied by the line's `native` list,
  which names the same words. The second states nothing twice, but it would make
  the print's own marking of a native form depend on the reader having listed it.
- Whether a face in standing prose stands, or every run comes to the editor
  (recommended).
- Whether *The Chukchee* is ever back-filled.
