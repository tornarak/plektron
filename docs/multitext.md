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
| `notation` | `jesup` | the transcription system its native forms are printed in |
| `dpi` | 300 | the resolution the PDFs place their masters at |
| `witnesses` | none | second copies, `{id, pdf, label}`, under `pdfs/witness/` |
| `omit` | none | leaves the *digitizer* added, never cut |
| `masterless` | none | leaves taken at their own size; the copy's, not the digitizer's |

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
stress accents (`Ӄaalbàт-éwҕан`) — and the layer flattens much of it
(`Қаават-éwђан`). Copy B's layer errs differently, word by word, which is what
makes it a second witness; both come from one engine, which is what makes it a
weaker one than it looks.

## Language tags

A tag may carry a script subtag: the 1900 book prints Chukchi in Cyrillic, and
`ckt-Cyrl` says so. Every membership test goes through `langs.is_tier1` and
`langs.is_known`, which read the base, because `"ckt-Cyrl" in TIER1` is False
and every gate on a Tier-1 span would fall silent on it with no error.
`test_tier1_scope.py` refuses a bare membership test anywhere outside
`langs.py`.

## Waits on the editor

- **The 1900 notation key.** The introduction states the notation; it is read
  off the rasters, ratified against them, and written to its own
  `keying_spec.md` section and to this text's `edition/alphabet.json`. Nothing
  about the notation is assumed before then, which is why `notation:
  kolyma-1900` names no tables yet.
- **The breve on Cyrillic `у`.** `ў` is a sort of the 1900 notation, and
  `detectors.MARK_LICENSE` licenses the breve on `u i и И` only, so `ocr
  restore` would refuse a line holding it. §2.6 says a further base is licensed
  only on attestation the editor has stamped; the key is that attestation.
- **The `ө` trap.** `ө` U+04E9 is a live letter of the 1900 notation and a §3
  lookalike for U+0275 in the Jesup one. It is worklist noise, never a block
  (`corpus normalize` blocks on NFD, licences and spacing only), and scoping it
  is §3's to rule.
