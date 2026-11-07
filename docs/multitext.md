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
thresholds in `lines.py` and `zones.py` still assume 300 dpi, and moving each
through it is the step before the zone track runs on this text.

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
