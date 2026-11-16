---
name: read-materials-page
description: Read pages of Bogoras's 1900 «Матеріалы» (jesup/bogoras-materials) into review/PP-NNN/proposal.json — two text-layer copies set side by side, the scan where they part, the Russian settled on its sense, and every native form read off the scan and listed for the editor. Use when reading, proposing or "doing" a page of the 1900 Materials, or on /read-materials-page PP-NNN. Not The Chukchee's pass — that is rebuild-groundtruth.
---

# Read a page of the 1900 *Materials*

The stores are under `jesup/bogoras-materials/`; run every command from there or
with `--root jesup/bogoras-materials`.

**The division of labour.** The book is ~95% Russian prose, set clean and read
near-clean by two OCR passes over two copies. Russian is outside the firewall
(CLAUDE.md): a model reading against the scan settles it. The native forms are
inside it: the reader keys them as read and lists them, and the editor rules on
every one. So the page's human cost is its native forms and its `doubt` lines,
nothing else.

**Why two copies are not two witnesses.** One engine read both, so the copies
share its habits. On `1-022` both set a space before every comma, where the print
has none, and both read `Ајңанват` where the print sets `Ајңан̀ва́т`. Agreement lets
a Russian line stand. It never settles a native form or a space.

## The pass, one page

1. **`harness ocr witness REF --witness b`** sets copy A's lines (`mz/ocr/`) beside
   copy B's, each `same`, `spacing`, `differ` or `alone`, with `native`: the
   tokens either copy reads as Tier-1 under this text's keying rules. A page the
   pairing could not settle (`ocr pair`) says so; leave it for the editor.
2. **Settle every line, and write every line** — the proposal holds the page,
   not its differences.
   - `same` and the Russian reads as sound pre-1918 prose: it stands.
   - `spacing`: the print's. §2.9 holds here: no space before `; : , ! ?`, and
     the print sets none before `.` or `)` either. The copies' spaces are the
     engine's, whichever copy has them.
   - `differ`, `alone`, or Russian whose sense does not hold (a wrong case, a
     non-word, a Latin letter inside a Cyrillic word — `Tоже`, `ОГЛАВЛЕНIE`,
     `миөологическаго` for `миѳологическаго`): read it at the scan with
     `harness ocr zoom REF N@P …`, all doubts in one call, 2× first.
   - Pre-1918 orthography as printed: `ѣ і ѳ ъ`, `-аго`, `по русски`. Never
     modernise, never correct the author. A compositor's slip is keyed as set,
     with a `print` note.
   - A speck the layer read as text is keyed empty, with an `artifact` note.
3. **Every native form is read off the scan, never off a layer.** Zoom each line
   that holds one. List the line's forms in `native`, space separated — every
   one, including those no glyph marks (`терк-арм` on `1-022`), since no rule can
   find those. Spell each form's codepoints in `resolved`, which `proposal check`
   holds the text to.
4. **The provisional keying conventions**, until the editor rules
   (`config/keying.json` `_glyphs` names the open questions):
   - A letter whose Latin and Cyrillic shapes are one shape in this face (`о р а
     е с у х`, `ј`) is keyed **Cyrillic**; Latin only for a shape Cyrillic lacks
     (`w`, `l`).
   - **Ruled by the editor off the scan (2026-11-07)**, so no `doubt` is needed
     for the letter itself:
     - folds in `config/keying.json`, which `ocr import`, `ocr witness` and
       `corpus normalize` write: hooked `К` is `ӄ`, hooked `Н` is `ӈ`, the
       layers' `ә` is a printed `э`, the palochka `Ӏ` is the tall `l`, the
       forked `d` (a serif D with two spurs, like an aquila) is `ð`, and `ä` is
       Cyrillic `ӓ`;
     - letters of the notation, keyed as the layers have them: `ђ` (a `ҕ`-like
       shape is `ђ` too), `һ`, `ѵ`, `с̧`, `ł` (the barred `l`), and the grave.
     A layer can still read a letter as another one, and a fold cannot reach
     that. Two cases are known so far: the forked `d` read as `ђ`, and the barred
     `l` read as plain `т` (`єта́` is `єłа́`, `1-102` l4). A plain `т` is printed
     in the same word elsewhere (`1-077` l12), so every `т` in a native form
     is a place to zoom.
   - **Not ruled:** an `є` with a hook below that is not a diacritic (`Кэ́lę`,
     `1-252` l7; the layers' `ę`), which is not the plain `є` of `Ђáðє`
     (`1-152` l4). Each is
     noted `doubt` where it occurs. **Never invent a codepoint**: an unknown
     letter is keyed as the nearer layer has it, and noted.
   - **The 1899 key** (`scratch/chukchi/bogoraz-1899-phonetics-key.md`; see
     `docs/multitext.md`, "Waits on the editor") says what a letter may be. It
     is not what the 1900 print sets, since that print pares the key's
     distinctions down. Where the scan shows a key letter the rules lack (`ҕ`
     beside `ђ`, `к̧`, `h̦`, `р̌`, a mark below `w` or `ы`, `^`), key it as the
     nearer layer has it and say in a `doubt` which key letter it looks like.
     Never key it from the key alone.
   - **The tall `l` is one letter however the layers read it**: `l`, `Ӏ`, `л`,
     `һ` or `I`. The editor found no visual distinction. One word can come out
     two ways: `эӈэӈыһын` and `эӈэӈылын` (`1-038` l37) are the same word set with
     `l`, and so are `-мэјӈэтыһыт` and `-мэјӈэтылыт` (`1-128` l8, l10). A `л` or
     `һ` inside a native form is a place to zoom. `һ` is also a real letter
     (`-чһын`), so the scan decides each one.
   - Accents are combining: acute U+0301 and grave U+0300 over the vowel or the
     consonant they sit on, as printed. The curly `’` between a native stem and
     its Russian ending is printed and kept.
   - Letterspacing (разрядка, the Russian emphasis, and the running head) is
     keyed unspaced, with a `layout` note on a body line, until
     `docs/rendition.md` is ruled.
   - **Footnote marks are keyed as printed** (the editor, 2026-11-16): the
     reference in the text is a raised digit and a full-size paren, `отчетѣ¹)`
     (superscripts U+00B9 U+00B2 U+00B3, U+2070–2079); the note's opener is
     full-size, `1) В. Г. Богоразъ…`. They are two glyphs on the page, so they
     are two in the keying. The layers read both as `1)`; the scan decides which.
   - **A line number in the margin is kept** (the editor, 2026-11-16), keyed in
     the line where the print sets it: before the text on a verso, after it on a
     recto, a space between (`5 Ајӈан…`, `…ва́т 10`). A number the segmenter cut
     as a line of its own is keyed alone on that line. Lifting it out of the
     text is the generator's work, by rule, not the reader's.
5. **A line still baffling after the scan carries a `note` of class `doubt`** —
   the only class that asks the editor for a ruling. Say what the two readings
   are, never which one "should" be right.
6. Write with `Write`, then send every field back through `harness proposal set`
   (`--values`) so it is NFD; `harness proposal check REF` must exit 0. The
   `contamination` block says `blind: false` and why: this pass reads both
   layers by design.

## What the editor does with it

The editor's queue on a page is its `doubt` lines and the forms in `native`,
nothing else. Each native form is a model's reading until the editor ratifies it
against the scan (`#llm` until then, whatever both copies say). What a page
contributes to this text's own dictionary is its `native` list, with the gloss
where the prose gives one — say so in a `semantic` note (`«людей солнечнаго
владыки»`).

`harness ocr review` shows each line's `native` forms and confines the page's
queue to those lines, the `doubt` lines and any line outside the prose alphabet;
the standing prose is shown dimmed and never saved as the editor's. Its keyboard
is this text's `config/keyboard.json`, phonetic Cyrillic with the notation's
letters.
