# Typeface sample, the rows behind `docs/rendition.md`

A model's reading of a fixed ten-page sample a book, off the 300 dpi scans, 2026-11-16. **Not ratified**: every row is `#llm`. One row was checked and corrected (`2-066` l42); the rest were not, so treat a row as a pointer to look at, not a reading. `docs/rendition.md` says how the pages were chosen and keeps the tallies; this file keeps the rows, so a tally can be checked against the scan. Line indices are the store's named in each part.

## Typeface tally — Bogoras, *The Chukchee*, ten-page sample

**Status: a model's reading of a sample (`#llm`-rank), not ratified.** Read off
`scans/chukchi-PP-NNN.png` directly, with `harness ocr zoom` (2x, gt store) on
1-066 (native forms, Latin quote, side-head), 1-350 (plate numerals) and 3-166
(heavy-looking words). Line = ALTO index from `harness ocr lines --store gt`.

Conventions of this tally:
- Native (Tier-1) forms are set in **roman** throughout the sample (confirmed at
  2x on 1-066 l4, l7); the notation letters ɪ etc. are excluded as instructed.
- The Latin quotation on 1-066 l12–13 is roman.
- Folios are roman old-style figures: ordinary roman, not counted.
- Running head "BOGORAS, THE CHUKCHEE." is all capitals, visibly smaller than
  body capitals — probably small caps throughout, but `ocr zoom` refuses
  apparatus lines, so not settled at 2x; recorded as `other (running head)`.
- Footnotes (and the 3-094 extract) are a **reduced-size roman** body. Recorded
  as one row per block, counted separately from the face runs.
- Heavier words on 3-166 l3 ("above all") and l7 ("Zashiversk") are ink gain —
  same letterforms as their neighbours at 2x; **not bold**.
- Figure captions (1-154 Fig. 35, rotated, with italic *a*, *b*; 2-140 Fig. 285)
  are not in `gt/ocr/` and are excluded.
- gt/ocr keys no face at all: every keyed column below is plain text.

### Face runs

| ref | line | face | as printed | gt/ocr keys |
|---|---|---|---|---|
| 1-066 | 0 BOGORAS, THE | other (running head, caps) | BOGORAS, THE CHUKCHEE. | BOGORAS, THE CHUKCHEE. |
| 1-066 | 8 MENTAL TRAITS | smallcaps (side-head) | Mental Traits. | MENTAL TRAITS. |
| 1-066 | 40–43 ¹ Nordenskiöld … | reduced-size roman (footnotes) | 2 notes | as printed |
| 1-154 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 1-154 | 3 of iron (Fig. 34 | italic (figure locant) | a | a |
| 1-154 | 6 the slanting base | italic (figure locant) | a | a |
| 1-154 | 9 (Fig. 34 | italic (figure locant) | b | b |
| 1-154 | 10 shaft. The upper piece | italic (figure locant) | b | b |
| 1-154 | 19 (Fig. 34 | italic (figure locant) | b | b |
| 1-154 | 20 of attachment | italic (figure locant) | b | b |
| 1-154 | 25 has a small wooden | italic (figure locant) | a | a |
| 1-154 | 25 has a small wooden | italic (figure locant) | b | b |
| 1-250 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 1-250 | 14 extract the fish-oil | italic (binomial) | Salmo sanguinolentus | Salmo sanguinolentus |
| 1-250 | 21 RAW AND PUTRID | smallcaps (side-head) | Raw and Putrid Meat and Carrion. | RAW AND PUTRID MEAT AND CARRION. |
| 1-350 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 1-350 | 11 SONGS AND DANCES | smallcaps (side-head) | Songs and Dances. | SONGS AND DANCES. |
| 1-350 | 17 Two or more girls | smallcaps (plate numeral) | xxvii | XXVII |
| 1-350 | 23 uttered (Plates | smallcaps (plate numeral) | xxxi | XXXI |
| 1-350 | 23 uttered (Plates | smallcaps (plate numeral) | xxvii | XXVII |
| 1-350 | 43 ¹ Boas | reduced-size roman (footnote) | 1 note | as printed |
| 2-066 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 2-066 | 42 “Wooden Spirits.” | italic (side-head) | “Wooden Spirits.” (italic inside printed quotes; the reader's first row omitted the quotes, corrected at 2× by the coordinator) | “Wooden Spirits.” |
| 2-066 | 43–44 ¹ Vol. VI … | reduced-size roman (footnotes) | 2 notes | as printed |
| 2-140 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 2-140 | 2 Stuck-in Poles. | italic (side-head) | Stuck-in Poles. | Stuck-in Poles. |
| 2-140 | 28 ¹ Compare p. 391 … | reduced-size roman (footnotes) | 3 notes, one line | as printed |
| 2-214 | 1 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 2-214 | 29 DIVINATION | smallcaps (side-head) | Divination. | DIVINATION. |
| 2-214 | 34 297, a) is used | italic (figure locant) | a | a |
| 2-214 | 34 297, a) is used | italic (figure locant) | b | b |
| 2-214 | 42–43 ¹ Compare … | reduced-size roman (footnotes) | 2 notes | as printed |
| 3-022 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 3-022 | 25 ADOPTION | smallcaps (side-head) | Adoption. | ADOPTION. |
| 3-022 | 42–44 ¹ Compare p. 45 … | reduced-size roman (footnotes) | 3 notes | as printed |
| 3-094 | 1 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 3-094 | 8–15 “When he left the camp | reduced-size roman (block quotation) | 8 lines | as printed |
| 3-094 | 21 THE VILLAGE OF | smallcaps (side-head) | The Village of the Maritime Chukchee. | THE VILLAGE OF THE MARITIME CHUKCHEE. |
| 3-094 | 40 The Boat-Crew. | italic (side-head) | The Boat-Crew. | The Boat-Crew. |
| 3-094 | 43–44 ¹ Bogoras … | reduced-size roman (footnotes) | 2 notes | as printed |
| 3-166 | 0 BOGORAS | other (running head, caps) | BOGORAS, THE CHUKCHEE. | same |
| 3-166 | 11 Anui Fair. | italic (side-head) | Anui Fair. | Anui Fair. |
| 3-166 | 43–44 ¹ Compare p. 652 … | reduced-size roman (footnotes) | 2 notes | as printed |

### Superscripts

| ref | line | kind | as printed | as keyed |
|---|---|---|---|---|
| 1-066 | 13 invicem interficiunt | footnote mark | ¹ | ¹ |
| 1-066 | 21 to the Chukchee | footnote mark | ² | ² |
| 1-066 | 40 ¹ Nordenskiöld | footnote mark (opener) | ¹ | ¹ |
| 1-066 | 41 ² Maydell | footnote mark (opener) | ² | ² |
| 1-154 | 3 of iron (Fig. 34 | figure locant | a³ | a³ |
| 1-154 | 6 the slanting base | figure locant | a⁴ | a⁴ |
| 1-154 | 9 (Fig. 34 | figure locant | b³ | b³ |
| 1-154 | 10 shaft. The upper piece | figure locant | b⁴ | b⁴ |
| 1-154 | 19 (Fig. 34 | figure locant | b⁵ | b⁵ |
| 1-154 | 20 of attachment | figure locant | b⁶ | b⁶ |
| 1-350 | 5 found by Parry | footnote mark | ¹ | ¹ |
| 1-350 | 43 ¹ Boas | footnote mark (opener) | ¹ | ¹ |
| 2-066 | 20 (ewyaˊnwɪčō) | footnote mark | ¹ | ¹ |
| 2-066 | 24 ascribe to them | footnote mark | ² | ² |
| 2-066 | 43 ¹ Vol. VI | footnote mark (opener) | ¹ | ¹ |
| 2-066 | 44 ² See Chapter XV | footnote mark (opener) | ² | ² |
| 2-140 | 3 (aᵋm-ɪˊnpɪn) | notation glyph | ᵋ | ᵋ |
| 2-140 | 3 of bone of whale | footnote mark | ¹ | ¹ |
| 2-140 | 23 chelson says | footnote mark | ² | ² |
| 2-140 | 27 had grass tied | footnote mark | ³ | ³ |
| 2-140 | 28 ¹ Compare p. 391 | footnote mark (opener) x3 | ¹ ² ³ | ¹ ² ³ |
| 2-214 | 10 as eiˊᵋut | notation glyph | ᵋ | ᵋ |
| 2-214 | 10 as eiˊᵋut | footnote mark | ¹ | ¹ |
| 2-214 | 34 “wooden spirit” | footnote mark | ² | ² |
| 2-214 | 42 ¹ Compare p. 479 | footnote mark (opener) | ¹ | ¹ |
| 2-214 | 43 ² Compare p. 341 | footnote mark (opener) | ² | ² |
| 3-022 | 18 mentioned | footnote mark | ¹ | ¹ |
| 3-022 | 24 knife and a brother | footnote mark | ² | ² |
| 3-022 | 38 in life.” | footnote mark | ³ | ³ |
| 3-022 | 43 ¹ Compare p. 45 | footnote mark (opener) | ¹ | ¹ |
| 3-022 | 42 ² Northly Archive | footnote mark (opener) | ² | ² |
| 3-022 | 44 ³ Kɪntaˊ-vaˊɪrg̣ɪn | footnote mark (opener) | ³ | ³ |
| 3-094 | 15 woman, who also came | footnote mark | ¹ | ¹ |
| 3-094 | 23 villages also have | notation glyph | ᵋ | ᵋ |
| 3-094 | 25 aᵋttooraˊlɪn | notation glyph | ᵋ | ᵋ |
| 3-094 | 36 occasionally a kind | footnote mark | ² | ² |
| 3-094 | 41 do with sea-hunting | notation glyph | ᵋ | ᵋ |
| 3-094 | 43 ¹ Bogoras | footnote mark (opener) | ¹ | ¹ |
| 3-094 | 44 ² Compare p. 387 | footnote mark (opener) | ² | ² |
| 3-166 | 20 constraint. “Many years | footnote mark | ¹ | ¹ |
| 3-166 | 38 on the Big River | footnote mark | ² | ² |
| 3-166 | 43 ¹ Compare p. 652 | footnote mark (opener) | ¹ | ¹ |
| 3-166 | 44 ² See Bogoras | footnote mark (opener) | ² | ² |

### Summary (model's reading of a sample)

No page is a plate or blank. Every superscript in the sample is keyed as printed.

| ref | lines | italic | smallcaps | bold | letterspaced | other (running head) | reduced-size blocks | superscripts |
|---|---|---|---|---|---|---|---|---|
| 1-066 | 44 | 0 | 1 | 0 | 0 | 1 | 1 | 4 |
| 1-154 | 44 | 8 | 0 | 0 | 0 | 1 | 0 | 6 |
| 1-250 | 44 | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| 1-350 | 44 | 0 | 4 | 0 | 0 | 1 | 1 | 2 |
| 2-066 | 45 | 1 | 0 | 0 | 0 | 1 | 1 | 4 |
| 2-140 | 29 | 1 | 0 | 0 | 0 | 1 | 1 | 7 |
| 2-214 | 44 | 2 | 1 | 0 | 0 | 1 | 1 | 5 |
| 3-022 | 45 | 0 | 1 | 0 | 0 | 1 | 1 | 6 |
| 3-094 | 45 | 1 | 1 | 0 | 0 | 1 | 2 | 7 |
| 3-166 | 45 | 1 | 0 | 0 | 0 | 1 | 1 | 4 |
| **total** | **429** | **15** | **9** | **0** | **0** | **10** | **9** | **45** |

Italic by use: 10 figure locants (1-154 x8, 2-214 x2), 4 run-in side-heads,
1 binomial. Smallcaps by use: 6 side-heads, 3 plate numerals (keyed uppercase).
Superscripts: 34 footnote marks, 6 figure locants, 5 notation ᵋ.

## Typefaces in Bogoras 1900, «Матеріалы», a ten-page sample

**Provenance: a model's (`#llm`) reading of a fixed sample, read off the 300 dpi
scans with 2x zooms where in doubt.** Not ratified. Pages: 1-021 1-022 1-023 1-064 1-154 1-178 1-200 1-246 1-336 1-426.
Machine text is `mz/ocr/` as printed by `harness ocr witness REF --witness b` (column a). Line indices are that store's.

Two things about the book's typography decide how to read the tables:

- **Letterspacing (разрядка, *razryadka*) is the only emphasis inside running text.** No italic or bold occurs in body prose on these pages.
  In the introduction (1-021..1-023) it marks **personal names** (Iokhel'son, Sibiryakov, Zaleman, Bogoras) and twice the word *Imperatorskago/Imperatorskoj* ["Imperial"].
  In the texts it marks **titles and headings** (tale titles, "Notes to No. N", "Proverbs"). Native Chukchi forms in running text are **never** letterspaced in this sample.
  The machine text records none of it: every letterspaced run appears as an ordinary word.
- **Notes, footnotes and "Recorded from…" lines are set in a second, smaller, condensed and heavier face** (here called *note face*).
  Native forms quoted inside that face are set in the wider body face (clearest on 1-154 and 1-200; on 1-178 the difference is in width and weight, the size difference is less sure).
  This is presumably because the special Chukchi sorts existed only in the body fount. That is an inference, not something the page states.

Italic occurs only in the note openers "(стр. N)" ["(p. N)"]. Bold occurs only in the section numbers ("19.", "27." …). No small caps occur.

### Runs not in ordinary roman body type

| ref | line | face | as printed (gloss) | machine text |
|---|---|---|---|---|
| 1-021 | 0 ВВЕДЕНІЕ | other (larger display capitals, page title) | ВВЕДЕНІЕ. ["Introduction."] | `ВВЕДЕНІЕ .` |
| 1-021 | 2 Сибирскимъ Отдѣломъ | letterspaced | Императорскаго ["Imperial (gen.)"] | `Императорскаго` |
| 1-021 | 3–4 …Сиби-/ряковымъ | letterspaced (across line break) | Сиби-ряковымъ [Sibiryakov (surname, instr.)] | `Сиби-` / `ряковымъ .` |
| 1-021 | 6 округѣ работали | letterspaced | Іохельсонъ [Iokhel'son (surname)] | `Іохельсонъ` |
| 1-021 | 7 шихъ обитателей | letterspaced | Іохельсонъ [Iokhel'son] | `Іохельсонъ` |
| 1-021 | 23–25 footnote | other (note face) | footnote 1: В. Г. Богоразъ, Краткій отчетъ… ["V. G. Bogoras, Brief report on the study of the Chukchi of the Kolyma region…"] | as plain lines |
| 1-021 | 23 1) В. Г. Богоразъ | letterspaced (in note face) | Богоразъ [Bogoras] | `Богоразъ` |
| 1-021 | 26 | folio (roman numeral at foot, body size, not a distinct face) | I | `I` |
| 1-022 | 0 | letterspaced (running head, small capitals) | В. Г. БОГОРАЗЪ, ["V. G. Bogoras,"] with folio II | `II В. Г. БОГОРАЗЪ ,` (line 1 `/` is noise) |
| 1-022 | 6 водчики Василій | letterspaced | Дауровъ [Daurov (surname)] | `Дауровъ` |
| 1-022 | 6 | letterspaced | Налетовъ [Naletov (surname)] | `Налетовъ` |
| 1-022 | 11 старался пользоваться | letterspaced | Ункуула [Unkuul (surname, gen.)] | `Ункуула` |
| 1-022 | 12 Егора Шамона | letterspaced | Шамона [Shamon (surname, gen.)] | `Шамона` |
| 1-022 | 12 | letterspaced | Атласова [Atlasov (surname, gen.)] | `Атласова` |
| 1-022 | 12 | letterspaced | Дьячкова [D'yachkov (surname, gen.)] | `Дьячкова` |
| 1-022 | 13 горія Чаина | letterspaced | Чаина [Chain (surname, gen.)] | `Чаина` |
| 1-023 | 0 | other (running head: small capitals, heavier, not letterspaced) | МАТЕРІАЛЫ ПО ИЗУЧЕНІЮ ЧУКОТСКАГО ЯЗЫКА И ФОЛЬКЛОРА. III ["Materials for the study of the Chukchi language and folklore." p. III] | `МАТЕРІАЛЫ ПО ИЗУЧЕНІЮ ЧУКОТСКАГО ЯЗЫКА И ФОЛЬКЛОРА . III` |
| 1-023 | 16–17 …К. Г. Зале-/мана | letterspaced (across line break) | Зале-мана [Zaleman (surname, gen.)] | `Зале-` / `мана ,` |
| 1-023 | 40 Въ Извѣстіяхъ | letterspaced | Императорской ["Imperial (gen. fem.)"] | `Императорской` |
| 1-064 | 0 | letterspaced (running head) | 8 В. Г. БОГОРАЗЪ, I,2. | `8 Г. БОГОРАЗЪ , 1,2 .` + line 1 `В.` |
| 1-064 | 3,8,13,18 (Chukchi) and 22,27,33,39 (Russian) | other (marginal line numbers, smaller) | 15, 20, 25, 30 (×2) — 8 runs | prefixed into the line, e.g. `15 lywаўӈонен…` |
| 1-154 | 0 | letterspaced (running head) | 98 В. Г. БОГОРАЗЪ, I,19. | `98 Г. БОГОРАЗЪ , 1,19.` + `В.` |
| 1-154 | 2 | bold (section number) | 19. | `19 .` |
| 1-154 | 3 | letterspaced (tale title, light face) | Melòта-lѵмӈыl. [Chukchi: "Hare tale"] | `Melòта - 1ѵмӈы .` |
| 1-154 | 7, 10 | other (marginal line number) | 5 (Chukchi side) | `5 ушакуч…` |
| 1-154 | 12 Записано | other (note face) | Записано отъ чукчи Ӄаðе на урочищѣ Сухарномъ осенью 1897 г. ["Recorded from the Chukchi Qade at the Sukharnoe site, autumn 1897"] | `Записано отъ чукчи Баде…` |
| 1-154 | 12 | other (native form in body face within note face) | Ӄаðе [personal name] | `Баде` |
| 1-154 | 13 | letterspaced (title) | Заячья сказка. ["Hare tale."] | `Заячья сказка .` |
| 1-154 | 17 | other (marginal line number) | 5 (Russian side) | `5 да)!…` |
| 1-154 | 22 | letterspaced (heading) | Примѣчанія къ № 19. ["Notes to No. 19."] | `Примѣчанія къ №19 .` |
| 1-154 | 23–26 | other (note face) | note 1 | plain |
| 1-154 | 23 | italic (note opener) | (стр. 1) ["(p. 1)"] | `(стр . 1)` |
| 1-154 | 27–31 | other (note face) | note 2 | plain |
| 1-154 | 27 | italic | (стр. 3) | `(стр . 3)` |
| 1-154 | 27 | other (native, body face in note) | ам-јомр-өттөөт нінэрэткін [Chukchi: "brings only willow bark"] | `ам-јомр-өттөөт нінэрэткін` |
| 1-154 | 27 | other (native, body face in note) | јомыр [Chukchi: willow-root bark] | `јомыр` |
| 1-154 | 32–35 | other (note face) | note 3 | plain |
| 1-154 | 32 | italic | (стр. 4) | `(стр . 4)` |
| 1-154 | 32 | other (native, body face in note) | Нутэ-ӈэўт [Chukchi: "Field woman", i.e. the fox] | `Нутэ-ӈэўт` |
| 1-154 | 34 | other (native, body face in note) | Куркыl [Chukchi: raven, "the croaker"] | `Куркы` |
| 1-154 | 34 | other (native, body face in note) | Lэјwvlын [Chukchi: wolf, "the wanderer"] | `Lájwvlын` |
| 1-154 | 34 | other (native, body face in note) | Мэшэтчы [Chukchi: bear, "living under the bank"] | `Мэшэтчы` |
| 1-178 | 0 | letterspaced (running head) | 122 В. Г. БОГОРАЗЪ, I,27. | `122 Г. БОГОРАЗЪ , 1,27.` + `В.` |
| 1-178 | 2, 6 | other (marginal line number) | 20 (×2) | `20 цынцам…`, `20 всѣхъ…` |
| 1-178 | 5 | other (note face) | Записано на р. Острокаменной отъ чукчанки Кутјэўт. ["Recorded on the Ostrokamennaya river from the Chukchi woman Kutjeut"] | plain |
| 1-178 | 5 | other (native, body face in note face; size uncertain) | Кутјэўт [personal name] | `Кутјэўт` |
| 1-178 | 8 | letterspaced (heading) | Примѣчанія къ № 26. ["Notes to No. 26."] | `Примѣчанія къ №26 .` |
| 1-178 | 9 | other (note face) | note 1: Сказка такого же характера, какъ и № 19 ["A tale of the same character as No. 19"] | plain |
| 1-178 | 9, 10, 13, 23 | italic (×4) | (стр. 1), (стр. 3), (стр. 6), (стр. 11) | `(стр . 1)`, `(стр. 3)`, `(стр . 6)`, `(стр . 11)` |
| 1-178 | 10–12, 13–22, 23–26 | other (note face, ×3) | notes 2, 3, 4 | plain |
| 1-178 | 10 | other (native in note) | ӄытó-kalélų [Chukchi: large caterpillar] | `ӄытó-kalélų-` |
| 1-178 | 11 | other (native in note) | kalчéђын [Chukchi: small brown beetle] | `калчеђын` |
| 1-178 | 13 | other (native in note) | кóрђылђын [Chukchi: small spider] | `корђыӄын` |
| 1-178 | 14 | other (native in note) | Кóрђылђы-ӈаўт [Chukchi: "spider woman"] | `Корђыӄы-ӈаўт` |
| 1-178 | 14 | other (native in note) | Тáӄі-нэўт [Chukchi: "Shining woman"] | `Такі-нэўт` |
| 1-178 | 20 | other (native in note) | áтаl-тéчірђын [Chukchi: syphilis] | `атаl-течірђын` |
| 1-178 | 21 | other (native in note) | áтаl-тáӈӈын [Chukchi: "Chuvan woman"] | `атаl-таннын` |
| 1-178 | 23 | other (native in note) | јáнрa-цájӄај рыкаврáwӄо [Chukchi: "around the lone rock one must go"] | `јанра-цајкај рыкаврашно` |
| 1-178 | 27 | bold (section number) | 27. | `27.` |
| 1-178 | 28 | letterspaced (title, ×2 columns) | Мцѐ-мцáнlыӈын. / Мцѐ-мрáнlыӈын. [Chukchi: "Mosquito-tale", women's / men's pronunciation] | `Мне - мцаныӈын . Мне -мранlыӈын .` |
| 1-178 | 29 | other (note face, ×2 column subtitles, not letterspaced) | Въ женскомъ произношеніи. / Въ мужскомъ произношеніи. ["In women's pronunciation." / "In men's pronunciation."] | plain |
| 1-178 | 33 | letterspaced (title) | Справляющій служеніе комаръ. ["The mosquito performing a ceremony."] | plain |
| 1-200 | 0 | letterspaced (running head) | 144 В. Г. БОГОРАЗЪ, I,44. | `144 Г. БОГОРАЗЪ , 1,44` + `В.` |
| 1-200 | 3, 6 | other (marginal line number) | 15 (×2) | prefixed |
| 1-200 | 4 | other (note face) | Записано отъ чукчи Рэмкылын'а на р. Молондѣ. ["Recorded from the Chukchi Remkylyn on the Molonda river"] | plain |
| 1-200 | 4 | other (native in note face) | Рэ́мкылын'а [personal name] | `Рэмкылын'а` |
| 1-200 | 8 | letterspaced (heading) | Примѣчанія къ № 43. ["Notes to No. 43."] | `Примѣчанія къ №№43 .` |
| 1-200 | 9–10, 11–12, 13–14 | other (note face, ×3) | notes 1–3 | plain |
| 1-200 | 9, 11, 13 | italic (×3) | (стр. 1), (стр. 6), (стр. 6) | `(стр. 1)`, `(стр . 6)`, `(стр . 6)` |
| 1-200 | 9 | other (native in note, ×3) | Ӄааlвàт-éwђан; Јáнөт-láўт; Јáаl-láўт [Chukchi names] | `Ӄаават-éwђан`, `Јанөт-láўт`, `Jáal-láўт` |
| 1-200 | 11 | other (native in note) | Чіђэ̀ј-вээм [Chukchi: "sand river", the Milky Way] | `Чіђај-вээм` |
| 1-200 | 13 | other (native in note, ×2) | Эм-нуӈ-іӄын [east wind]; эӈэ́нэӈэ [the same] | `Эм-нуӈ-іӄын`, `энэнэнэ` |
| 1-200 | 15 | bold (section number) | 44. | `44.` |
| 1-200 | 16 | letterspaced (title) | Вáырђу-wéthaw. [Chukchi: "everyday words", proverbs] | `Ваырӄу -wérhaw.` |
| 1-200 | 21 | other (note face) | Отъ разныхъ лицъ. ["From various persons."] | plain |
| 1-200 | 22 | letterspaced (title) | Пословицы (бытовыя слова). ["Proverbs (everyday words)."] | plain |
| 1-200 | 28 | letterspaced (heading) | Примѣчанія къ № 44. ["Notes to No. 44."] | `Примѣчанія къ №44 .` |
| 1-200 | 29–30 | other (note face) | note | plain |
| 1-200 | 29 | other (native in note) | Вáырђу-wéthaw | `Ваырђу-wéthaw` |
| 1-246 | 0 | letterspaced (running head) | 190 В. Г. БОГОРАЗЪ, II,72. | `190 Г. БОГОРАЗЪ , II,72 .` + `В.` |
| 1-246 | 2 | bold (section number) | 72. | `72.` |
| 1-246 | 3 | letterspaced (title, Chukchi + Russian) | Мéтыӈо-lѵмӈыl. О Мéтыӈо сказка. [Chukchi "Metyngo tale". Russian "Tale about Metyngo."] | `Метыӈо - 1ѵмны . О Метыӈо сказка .` |
| 1-246 | 34, 35–36, 37 | other (note face, ×3 footnotes) | 1) Собств. имя. ["Proper name."]; 2) Ӄон-реðóта. Чукчи любятъ втягивать руки… ["Chukchi like to draw their arms inside the fur shirt…"]; 3) Не знаю! ["I don't know!"] | plain |
| 1-246 | 35 | other (native in note) | Ӄон-реðóта | `Кон-редота.` |
| 1-336 | 0 | letterspaced (running head) | 280 В. Г. БОГОРАЗЪ, II,105. | `280 Г. БОГОРАЗЪ , II ,105 .` + `В.` |
| 1-336 | 21 | other (note face) | Записано отъ чукчи Ӈырóн'а на урочищѣ Аконáјке. ["Recorded from the Chukchi Ngyron at the Akonajke site"] | plain |
| 1-336 | 21 | other (native in note face) | Ӈырóн'а [personal name] | `Нырон'а` |
| 1-336 | 22 | bold (section number) | 106. | `106.` |
| 1-336 | 23 | letterspaced (title, light face; spacing slight) | Кэlílђу. [Chukchi: monster's name] | `Kəliljy .` |
| 1-336 | 36, 37, 38 | other (note face, ×3 footnotes) | 1) Междометіе. ["Interjection."]; 2) Стараясь увеличить свою силу. ["Trying to increase his strength."]; 3) Волкъ или что? ["A wolf or what?"] | plain |
| 1-426 | 0 | letterspaced (running head) | 370 В. Г. БОГОРАЗЪ, II,138. | `370 В. БОГОРАЗЪ , II,138.` + line 1 `Г.` |
| 1-426 | 38–39, 40 | other (note face, ×2 footnotes) | 1) Третій желудокъ оленя… ["The reindeer's third stomach…"]; 2) Выраженіе изумленія. ["Expression of astonishment."] | plain |

Checked and **not** letterspaced: every native form in running text (e.g. Ајӈаӥва́т, терк-арм-ора́weðат on 1-022; энэ́ӈэlыӈа, аӈа́ӈылы-ва́ырӄын on 1-023; Мéтыӈо on 1-246; Кэlílђу in 1-336 prose; Lólђылын on 1-426); "Императорской" on 1-023 line 18 (only line 40 is spaced); the Chukchi text block of 1-064. The spaced hyphens in "стану - ли", "только - что" (1-336) are justification spacing, not razryadka.

### Superscripts

| ref | line | kind | as printed | machine text |
|---|---|---|---|---|
| 1-021 | 9 работъ изложены | footnote mark in the text | отчетѣ¹) (raised 1, full-size paren) | `отчетѣ 1) .` (baseline) |
| 1-246 | 18 рику: «Я пришлю | footnote mark in the text | Мéтыӈо¹)» | `Метыӈо ¹)` |
| 1-246 | 27 черезъ него | footnote mark in the text | рукавъ²) | `рукавъ³)` — **wrong digit** |
| 1-246 | 30 кинули?» | footnote mark in the text | «Ӄо³)! | `«Ко³) !` |
| 1-336 | 7 «Ӄыч | footnote mark in the text | «Ӄыч¹)! | `«Быч 1) !` (baseline; Ӄ read as Б) |
| 1-336 | 17 Домой пришелъ | footnote mark in the text | камни²) | `камни 2)` (baseline) |
| 1-336 | 25 звѣрь | footnote mark in the text | звѣрь³) | `звѣрь³)` |
| 1-426 | 10 кажется, хорошо | footnote mark in the text | желудковъ¹) | `желудковъ 1)` (baseline) |
| 1-426 | 25 потомъ проснулся | footnote mark in the text | «Кáко мэ́ј²)! | `«Како мај²)!` |

Note openers ("1)", "2)" … at the head of each footnote, and "1 (стр. 1)" in the Notes) are **not** superscript: they sit on the baseline in the note face. No other superscripts.

### Summary per page

Columns count runs. "spaced-body" means letterspacing in running prose or a note. "spaced-head" means the running head. "spaced-title" means titles and headings. Note-face blocks are counted one per note or footnote, the "Recorded from…" lines and subtitles included. "native-in-note" counts native forms set in the body face inside note-face text. "margin no." counts marginal line numbers. Lines are `mz/ocr` TextLines, noise included.

| ref | lines | spaced-body | spaced-head | spaced-title | italic | bold | smallcaps | display title | note-face block | native-in-note | margin no. | other head | superscript |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1-021 | 27 | 5 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| 1-022 | 42 | 7 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1-023 | 41 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| 1-064 | 41 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 |
| 1-154 | 36 | 0 | 1 | 3 | 3 | 1 | 0 | 0 | 4 | 7 | 2 | 0 | 0 |
| 1-178 | 36 | 0 | 1 | 4 | 4 | 1 | 0 | 0 | 7 | 9 | 2 | 0 | 0 |
| 1-200 | 31 | 0 | 1 | 4 | 3 | 1 | 0 | 0 | 6 | 8 | 2 | 0 | 0 |
| 1-246 | 38 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 3 | 1 | 0 | 0 | 3 |
| 1-336 | 39 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 4 | 1 | 0 | 0 | 3 |
| 1-426 | 41 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 2 |
| **total** | **372** | **14** | **8** | **13** | **10** | **5** | **0** | **1** | **27** | **26** | **16** | **1** | **9** |

Per-face totals: letterspaced 35 (14 in running text or notes, 8 running heads, 13 titles and headings); italic 10 (all "(стр. N)" note openers); bold 5 (all section numbers); smallcaps 0; other 71 (1 display title, 1 unspaced capital running head, 27 note-face blocks, 26 native forms in body face inside notes, 16 marginal line numbers); superscripts 9. The mz/ocr text records none of the face distinctions. It sets 4 of the 9 superscripts as baseline "N)" and gives 1 of the other 5 the wrong digit.
