# More than one text

The workspace `jesup/` holds two texts now: *The Chukchee* (`bogoras-chukchi/`,
stem `chukchi`) and Bogoras's 1900 Kolyma *Materials* (`bogoras-materials/`, stem
`chukchi-materials`). The plumbing that composes a text over its workspace —
`layout.shared`, per-text ratification, stem-qualified citations, `site build` —
is `layout.py`'s and `docs/edition.md`'s. This file owns what a second text
added.

## What a manifest declares

Each field is optional, and absent means what *The Chukchee* has always meant,
so the first text's manifest needed no edit. `layout._project` checks them all.

| field | absent means | what it is |
|---|---|---|
| `lang` | `en` | the language of the book's prose. Never a Tier-1 code. |
| `dpi` | 300 | the resolution the PDFs place their masters at |
| `witnesses` | none | second copies, `{id, pdf, label}`, under `pdfs/witness/` |
| `omit` | none | leaves the *digitizer* added, never cut |
| `masterless` | none | leaves taken at their own size; the copy's, not the digitizer's |
| `prose_stands` | nothing stands | the editor's ruling, in words, that plain prose may reach `gt/ocr/` on a model's reading |

`omit` and `masterless` are two rules, not one with two names. A QR code or a
Google usage notice is no part of the book or of the copy, so it is never read.
A library's own cover or flyleaf belongs to the copy, so it is cut, at its own
size and in its own colour space (`1-003` is grey, *The Chukchee*'s three are
RGB). `1-002` was first put under `masterless` and the carve-out's own check
refused it: it does carry a master at scale. That is the check working.

A witness lives under `pdfs/witness/` because `scans` matches part names by
substring over `pdfs/*.pdf`, and copy B's filename contains copy A's.

## Resolution

`scans extract` takes the text's `dpi` for the scale test and records it in
`data/pdf_images.json` as `_dpi`; `scans swap` refuses a tree cut at another
resolution, because a shift plan cannot express a factor of two. Rasters are
kept at 600 dpi rather than decimated: a 2:1 resample of a bitonal master is a
render, and `scans/` is cut, never rendered. `layout.px(root, n)` scales a
300-dpi-calibrated pixel threshold to the text. **No caller uses it yet**: the
thresholds in `lines.py` and `zones.py` still assume 300 dpi. The 1900 text's
zones are not meant to wait on that move ("Zoning by rule", below), but any
raster-reading check run on it does.

## The text layer

`harness ocr import` carries the master PDF's own OCR layer into `mz/ocr/`, in
`ocr predict`'s page shape, so the ladder runs on unchanged from `ocr-mz`. The
layer's fragments are rebuilt into rows by rule (`textlayer.ROW_OVERLAP`); boxes
are the layer's points less the master's placement origin, times `dpi / 72`.

**`kind: model`, and the PDF is the model.** The glyphs were inferred from a
raster by the digitizer's OCR, and the importer only carries them; `kind` names
the witness to the content, so it is a model's, with the PDF as its checkpoint by
path and digest. `fig propose` is a rule because an image placement is a fact of
the PDF; a glyph in its text layer is a guess.

**The boxes are font metrics, not ink.** Checked on printed p. 144 (`1-200`)
with `ocr sheets`: every crop holds its whole line. The running head splits —
"В." falls out of its row, being set in another size — and the layer's own
space before punctuation comes through as the OCR read it.

**But the boxes drift against the scan, and the import corrects it.** The
master is placed at exactly `dpi / 72` on every page, yet the layer's boxes sit
up to ~100 px off the ink by a page's foot, by an amount that differs page to
page, runs both ways, and can differ between the body and its footnotes: the
digitizer's OCR placed its words with a drift of its own. A zone's edge drawn
from a drifted box cut off the ink of the line it held (`1-440`), and a page's
source note looked like a line with no row (`1-243`). `ocr import` moves each
box vertically onto the ink (`textlayer.align`: a line fitted down the page
through each full row's baseline-to-ink offset, then a shift per block of rows),
recording the fit; `VERBS.md` has the method. Over the 451 text pages, rows
sitting on another line's ink fell from 770 to 161, and the zones' uncovered
wide bands from 65 to 48. The residue is mostly footnotes that follow the body
with no gap (`1-299`), which the `uncovered` flag sends to the review pass.

**The layer is unreliable exactly where the firewall says it will be.** The
printed Chukchi mixes scripts inside a word — a hooked `Ӄ`, Latin `a l w j`,
stress accents (`Ӄaalbàт-éwђан`) — and the layer flattens much of it
(`Қаават-éwђан`). Copy B's layer errs differently, word by word, which is what
makes it a second witness; both come from one engine, which is what makes it a
weaker one than it looks.

## Keying rules, workspace over text

The tables every gate reads — the inventory, the lookalike traps at their three
scopes, which bases a mark is licensed on — are data: `config/keying.json`, at
the workspace and optionally at the text. `layout.layered` composes them as an
object over its prototype, **key by key**: a text names only what its book does
differently, inherits every key it does not name, replaces a leaf it does, and
removes one with `{"_delete": why}`. `keying.rules(root)` is the one place the
tables are built, and every reader takes the result as an argument rather than
reading a module constant (`test_keying.py` refuses one). `corpus rules` shows a
text's effective table and which tier set each entry.

There is no code layer beneath the workspace's. A notation held in code would be
handed to every workspace, including one whose books were never printed in it,
and a workspace with no rules is refused rather than defaulted.

**A text's override is a ruling, and says so.** Each leaf it sets or deletes has
an entry in its `_why` naming the attestation (`keying_spec.md` §2.6: "licensed
only on attestation the editor has stamped"); an unattested override, or a `_why`
for nothing the text sets, is refused. A text with no workspace layer beneath it
is its own base and attests nothing, since it overrides nothing.

**A file is judged by the rules of where it lives.** `corpus normalize` reaches the
workspace's shared stores (`../edition/entities/`) from a text; those are held to
the workspace's rules alone, because a file every text reads cannot take the
rulings of whichever text happened to run the scan. `keying.rules_for` decides.

The manifest's `notation` field is retired and refused: the rules *are* the
notation, and a name beside them would be the same fact stated twice.

## Language tags

A tag may carry a script subtag: the 1900 book prints Chukchi in Cyrillic, and
`ckt-Cyrl` says so. Every membership test goes through `langs.is_tier1` and
`langs.is_known`, which read the base, because `"ckt-Cyrl" in TIER1` is False
and every gate on a Tier-1 span would fall silent on it with no error.
`test_tier1_scope.py` refuses a bare membership test anywhere outside
`langs.py`.

## Witness B, and the reading flow

Copy B (`pdfs/witness/`) is a second reading of the same print by the same
engine on another scan. `ocr pair` maps each copy-A page to its copy-B page by
the text alone, never by index; a page that matches two (copy B scanned pp. 2–3
twice, so 1-058 and 1-059 do) is named and settled by the editor in the witness's
`map` in `project.json`, never chosen. `ocr witness` then sets the two copies'
lines side by side and names the native forms in each.

The reading over that: where both copies agree and the Russian is sound, the
line stands; where they differ, or the sense does not hold, the reader settles it
at the scan; a line still baffling after that carries a `note` of class `doubt`.
The native forms on every line go to the editor, whatever the reader thought of
them: the reader lists them in the line's `native` field, including the ones no
glyph marks, which no rule can find. The pass is `/read-materials-page`.
`1-022` is the first page read this way. One engine read both copies, so their agreement is weaker than
it looks (`docs/decisions.md`) — which is why agreement lets a Russian line stand
and never a native form.

**The prose reaches ground truth on the reading.** The editor ruled it for this
text on 2026-11-07, and the ruling sits in `project.json` as `prose_stands`.
`ocr restore` lets a proposal line stand without a decision when it lists no
`native` form, carries no `doubt`, and holds only letters of the
`prose_alphabet` (`review.standing`, `detectors.prose_only`). A human decision
always overrules a standing line, and the restore report's `stood` names every
line that went in on the reading. Which lines stood is derived from the tracked
proposal on each run and stored nowhere, so `decision.json` stays a record of
human acts. `prose_only` admits a line, it does not select tokens, so a native
form no glyph marks (`терк-арм`) passes it. Only the reader's `native` list
keeps such a form for the editor.

## Zoning by rule, off the text layer

The editor's call (2026-11-07): the 1900 book is set formulaically enough that
its zones can be derived from `mz/ocr/` (the text layer's rows, `ocr import`)
and the scan, so no segmenter is trained on it and none is keyed from scratch.
**`harness zones propose`** is that derivation (`harness/zones_rule.py`). It is
a **rule**, so its output goes to `mz/zones/`, `#mz`, with `kind: rule` and
every threshold it used in its provenance, and it reaches `gt/zones/` only
through `zones edit`, where the editor ratifies or corrects each page. The
thresholds are this book's, in its `config/zones.json` `text_rule` block, each
beside what it was measured on: `ocr lines` over all 451 text pages, the rule's
own report, and six pages read band by band (`1-021`, `1-022`, `1-100`,
`1-177`, `1-200`, `1-205`).

What the rows show (600 dpi), and what the rule does with it:

- **Two column measures.** The column is ~2980–2995 px wide on every full row,
  and its left edge moves with the scan. Zones span the ink-anchored window
  `zones check` holds them to; the indent, centring, a margin number and the
  gutter search are read against the rows' own column, the median left edge of
  the full rows. The two differ by the font-metric-to-ink offset, 33–38 px on
  five of the six pages, which is reported and gates nothing.
- **A line, not a row, is the unit.** The layer can leave two rows on one
  printed line (the head's `В.`, set in another size; a broken row), and rows
  whose centres coincide are one line. Neighbouring full lines overlap often and
  harmlessly: a quote mark or an accent makes a box ~150 px tall against ~100,
  and 852 adjacent pairs overlap by more than 16 px. So overlap refuses nothing,
  and where two bands' lines overlap they meet at the midpoint.
- **A speck** (a row with no letter or digit: `/`, `.`, `-`) is left unzoned, so
  it cuts no gap.
- **The running head** is the first line when it starts above y = 700 (449 of
  451 pages); the chapter openers have none.
- **A paragraph's first line** is indented ~210 px. The line before one is often
  short, but a full line can end a paragraph too, so only the indent is evidence.
- **A heading** is a short line centred in the column (`7.`, `Бумнін ваырӄын.`,
  `Примѣчанія къ №43.`, all within 20 px of centre). No gap is required: `44.`
  sits 86 px over its title.
- **A gap of 80 px or more ends a band.** It is the break that nothing else
  marks: on a **Section I** page the Chukchi runs first, then its Russian
  translation full-width, each continuing from the page before, and the
  Russian often resumes unindented under a rule the layer does not read (87–300
  px). Leading within a stream reaches 61–63 px in the front matter and
  dialogue.
- **The footnotes** open `N)` under the footnote rule: a short printed rule
  from the column's left edge, found as the longest horizontal ink run in the
  gap above (a line of type never makes one). Every one of the 188 blocks
  opening `N)` under a gap carries one, 513–999 px from within 213 px of the
  edge, and none of the six that are not footnotes does (the proverbs of
  `1-200`, the numbered texts of `1-201`, `1-202`). The block and everything
  below it is the apparatus: on `1-048` the two documents a footnote introduces
  are printed in it. Where no rule is found, the last block opening `N)` is
  still footnotes if it is set smaller (a pitch of ~95–110 px against the
  body's ~120–130). Pitch alone missed `1-278`, whose two notes run at the
  body's pitch. The in-text call is no witness: the layer drops its digit
  (`зимушку )`, `1-216`).
- **A full-width rule** separates the Chukchi from its Russian on a Section I
  page (~2940–2985 px). A `MainZone-Continued` band under one is expected and
  raises no `continued` flag.
The editor's rulings on what each of this book's structures is zoned as — margin
line numbers, the *Примѣчанія* notes, parallel columns, foot matter — are
`.claude/skills/review-zones/rulings.md`, their one home, since the review agent
carries that file whole. What the rule does to follow them:

- **Foot matter**: walking up from the last line, up to two lines that are a lone
  number or numeral, at most 200 px wide and inside the column.
- **Margin numbers**: a number leading a row that starts 40 px or more left of
  the column, or trailing one that ends as far right (`5 чашчушачһын…`, 60–104 px
  left; `… нумэкэт- 5`, a row 3102 px wide against the 2990 px measure, on a
  recto), or a row of its own outside the column (`15`, `1-177` l34). The line is
  measured as if the number were off it.
- **The notes**: the page is in them from a «Примѣчанія къ №» heading, or from
  its top when its first marker is an opener (a note carried over), until a
  heading that is not a notes heading. In them, only an opener or an indented
  fresh line starts a band. **The rule reads one page at a time**, so a page
  wholly inside one long note shows neither sign and falls to the indent rule.
- **Parallel columns**: the text layer reads each row across both columns
  (`1-177` l8: `Эпээ - цэмкын нумэкэткін, ъмыló Энээ-рэмкын нумэкэткін, ъмыó`), so
  the band is found by the gutter, a vertical white run through the band's middle
  on the scan, which the rows cannot show: three or more lines sharing one at
  least 60 px wide, with ink on both sides of it in each line, within 300 px of
  the column's centre. The parallel texts' gutters measure 63–113 px and sit
  within 18 px of centre (`1-172`–`181`, `1-202`–`211`), and the two-column billet
  on `1-048` at +216; the one river of word spaces that lines up over three lines
  (`1-351`) sits at +443. **Two lines are not enough**, so the oath's two-line
  tail on `1-205` is not found.

The text layer joins margin marks to rows: `1-100` l13 spans 4220 px from
x = −6 because a `}` in the margin opens it. A row that overhangs the column on
one side by more than 40 px, with a token of at most three characters at that
end, carries a margin mark, and is measured as if the mark were off it: 13 of
the 14 rows rule version 2 found too wide were one (`зо` for 30, `5.`, `-70`,
`/`, `}`, `L`, `T`, `•`). A line still wider than the column is reported and
left unzoned, and the band it falls in ends there; the one left is `1-088` l8,
whose number the layer fused into the word (`30јанөт`). It is not split by
guesswork.

**The review pass, between the rule and the editor.** The editor read the rule's
output on six pages and found it sound, with rough edges an agent could smooth.
An agent's edit is `#llm`, so it cannot live in `mz/`, which the next `propose
--force` regenerates: it lives in `review/PP-NNN/zones.json`, tracked, as edits
against the rule's numbered bands (relabel, merge, split at a line, absorb an
unzoned line), each with its reason, and naming the rule file's digest so it goes
stale visibly. `zones verdict` gates it; `zones edit` shows it applied in the
`llm` view, and a human save is still what writes `gt/zones/`. The rule records
`flags`, its page-level reasons a band may be wrong (`unzoned`, `parallel`,
`notes`, `continued`, `fallback`), and `zones queue --all --sample N` deals
those pages out with N unflagged ones beside them. The agent reviewed the rule's
output, so its agreement is not a second witness. Dispatch is
`.claude/skills/review-zones/`, the contract `.claude/agents/zones-reviewer.md`.

**Open for the generator, not the zones:** two streams on one page means a
page-top `MainZone-Continued` can continue either of them. `tei generate` joins
a continuation to the page before's last paragraph, which on a Section I page is
the Russian, while the page's first band is the Chukchi. Nothing in the zones
says which band is which stream: both are `MainZone-Continued`. Whether the
stream becomes a label, a field, or something the generator reads off the
order is undecided, and it is not the rule's to decide.

## Waits on the editor

- **The 1900 notation key: found in the 1899 «Образцы», not yet reconciled with
  the reading.** The 1900 book prints no key. Its introduction (1-023, p. III)
  says only that the transcription "was changed and simplified on Academician
  Salemann's instructions". Bogoras's 1899 «Образцы матеріаловъ…» (*Извѣстія ИАН*
  X, 3, pp. 269–318; mathnet.ru im4641) opens with one: §§ 1–10, «Предварительныя
  замѣчанія о фонетикѣ», pp. 270–275. The PDF, its page images and a transcription
  of the key (#llm, by page) are in `scratch/chukchi/` (`bogoraz-1899-*`,
  `obraztsy-1899/`), which is untracked.
  - It is the same author's key to the same notation, but another publication:
    evidence about the 1900 book, not the book's own apparatus.
  - **The 1900 text tends to pare down distinctions the key draws** (the
    editor, 2026-11-07). So a letter the key lists is not presumed in the
    1900 print. Each one is reconciled against the scan as pages are read, and
    the keying rules change only on that reading.
  - The questions it raises:
    - `ҕ` and `ђ` are two letters in the key, and the OCR reads both as `ђ`.
    - The key says Chukchi has no hard л, so any `л` in a native form may be `l`.
    - The grave marks secondary stress on a vowel and softness on a consonant.
    - `ł` is t + l and `ď` is dl, values found after the editor chose `ł` and `ð`.
    - The key lists letters the 1900 rules lack: `к̧`/`wк̧`, `h̦`, `р̌`, nasal
      `w̰` and `ы̨`, and the marks `^ ˘ ¯`.
    - The hooked `є` may be §8's nasal hook.
  - Book-internal evidence binds meanwhile: 1-098 l46 calls the acute stress;
    1-175 l29 names `с̧` beside ч.
- **The letters still unruled.** The editor classified the text's letters off the
  scan on 2026-11-07. The rulings and their evidence are in the 1900
  `config/keying.json`.
  - Folds: hooked `К` is `ӄ`, hooked `Н` is `ӈ`, the layer's `ә` is a printed `э`,
    the palochka is the tall `l`, the forked `d` is keyed `ð` (its sound unknown),
    and `ä` is Cyrillic `ӓ`.
  - Letters of the notation: `ђ` (the `ҕ`-like letter is `ђ` too), `һ`, `ѵ`, `с̧`,
    `ł` (the barred `l`, Polish for its sound) and the grave.
  - Still open: an `є` with a hook below that is not a diacritic (the layer's `ę`;
    plain `є` is a separate letter). The "barred `т`" was the barred `l`, which
    the layer reads as plain `т` (`єта́` for `єłа́`, 1-102 l4). A real `т` is
    printed in the same word elsewhere, so no fold can separate them. None needs to be ruled before
    review: `prose_alphabet` (below) sends every form carrying one to it.
  - The tall `l` has no codepoint of its own in the layer, which reads it as `l`,
    `л`, `һ` or `I` as well as the palochka. Only the palochka is folded, since
    Russian prose sets the other three legitimately.

## Rules that are switches, not glyphs

Three tables hold rules rather than characters. **`detectors`** names the checks a
notation runs, from the closed set `keying.DETECTORS`: word-medial `[AEIL]`,
dot-above-g, the bare-g suffix and the straight apostrophe as a mistyped stress
are each one notation's facts, so a book that prints none of them deletes the
switch. **`tier2_scripts`** names scripts no token of which is Tier-1: *The
Chukchee*'s Russian is Tier-2 prose, so `Cyrl` is there in the workspace, and the
1900 book, which prints its Chukchi in Cyrillic, deletes it. **`prose_alphabet`**
names a script's prose letters; in a token of that script any other letter or
mark is notation, or an error — an exclusion list, so a glyph nobody listed is a
loud question. The 1900 text declares the pre-1918 Russian alphabet, leaving out
`ѵ` (a letter of its native forms) on purpose. Every Tier-1 selection —
`bears_inventory`, `detect_all`'s inventory arm, the native-corpus prior, the
batch, the generator's handles — reads the result, so they still agree.

The 1900 text's rulings, each with its leaf in `_why`: `ө` unflagged in the four
trap tables; the curly `’` it prints between a native stem and a Russian ending
(`Ајңаѝва́т’омъ`, 1-022) is no trap, and a straight `'` is a slip for it; the acute
and grave are notation; all four detectors are off.

**`folds`** maps what an OCR emits for a sort to what the editor identified it
as. Each side is a letter, or a letter and its marks, in NFD, so `ď` (d + U+030C)
folds to one `ð`. The 1900 text has six, each with its capital: `қ`→`ӄ`, `ң`→`ӈ`,
`ә`→`э`, the palochka `ӏ`→`l`, `ď`→`ð` and Latin `ä`→Cyrillic `ӓ`. Each fold is
an identity, so only the editor's ruling may add one. It takes the longest key
first, and it never chains or lands on a lookalike trap. It is applied wherever text enters
a store: `ocr import` (and its producer records the folds), `ocr witness` for
both copies, and `corpus normalize`, which reports an unwritten fold as blocking
and writes it under `--commit`. Normalize never folds `config/`, whose rulings
name the codepoints they fold.
