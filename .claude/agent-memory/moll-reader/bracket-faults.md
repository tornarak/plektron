---
name: bracket-faults
description: A numbered bracket is a guess by the measurement tool, not a fact — it can hold no entry, part of one, or six; check what is inside every bracket, not just the page total
metadata:
  type: project
---

The marked page's numbers come from measuring ink, not from reading it. Every
one is a prediction that **this bracket holds exactly one flush-left bold
lowercase headword with a gloss**. Test that for each bracket. The page total
agreeing with the prediction proves nothing, because two faults on one page can
cancel (moll-036 lost two brackets and came out 41 against 43).

**The count can be wrong in both directions.** Everything below except the last
case makes it too high; the wrap band makes it too low.

| what the bracket really holds | seen on | keep the row? |
|---|---|---|
| a quire mark — digits and a dash, no Cyrillic (`З—561`, `3*`) | moll-034, moll-036 | no |
| an illegible blot with no Cyrillic and no gloss | moll-052 | no |
| an all-caps fragment with no gloss (`ГЫТ ТЫ`) | moll-036 | no |
| several complete entries under one label — one wrap plus **five** headwords | moll-035 | one row each |
| three headwords stacked under one label, no `←` — three flush-left bold words, three glosses, on three consecutive lines of the same bracket | moll-091 | one row each |
| two headwords, no `←` between them | moll-059, moll-095 | one row each |
| two headwords, second **not** flush-left — bold, matching headword weight, run into the tail of the first entry's gloss line instead of starting a new line (`ныкынмальав 1) согласно; 2) поровну; ныкынмальав вальын 1) единый; ...`) | moll-087 | one row each |
| a wrapped tail **plus** the next headword, swallowed by the `←` band | moll-053 | one row each |
| bold text mid-line, not flush-left — a derived form's mini-gloss | moll-033 | keep inside the gloss cell |

**Withhold a row on what you can see, never on what you infer the mark to be.**
On moll-052 a reader called a blot a quire mark on shape and position and wrote
that as a general rule; a human adjudicated it as an ink smudge. No bold
Cyrillic headword and no gloss is already sufficient — say that in `disagrees:`
and stop. Naming the mark adds a claim you cannot support, and in memory it
licenses the next reader to skip a bracket on shape alone.

**The swallowed headword is the one that costs an entry.** When the context
block names a wrapped entry, read the whole continuation band, not just enough
of it to finish the definition: on moll-053 the `←` band over the tail of
`килвэй` also covered `килвэйык проводи́ть пра́здник рого́в`, a full headword
with its own gloss, and the next numbered bracket was the entry after it. A
reader trusting the total keys 47 rows and silently drops a real entry.

**The tells, before you read closely:**

- a `zoom STEM:N` crop several times taller than its neighbours (moll-035's was
  1170px against a normal 130–320px) means more than one headword inside;
- a bracket alone at the foot of a column, especially the last before the column
  ends, is where quire marks sit;
- a bracket named in a wrap warning may extend past the tail it was drawn for.

**Then count your own file before you report it.** The moll-053 reader wrote 48
rows and reported "47, matching the prediction exactly" — it had found the fault
and did not notice, so it wrote no `disagrees:` and the store carried an
unexplained count until a corpus-wide check caught it. Match your report against
the table you actually wrote, never against the prediction. **A silent agreement
is worth less than a stated disagreement**, and a row count differing from the
prediction by more than one is expected and correct when a bracket held several
entries — not evidence you have erred.

**A bare `(2)` right after the headword is not a sense numeral, not a torn
entry, and not a bracket fault.** It is the book's strong-vowel-row marker and
it belongs verbatim at the head of the gloss cell — the whole account, and the
three separate times a reader invented a meaning for it, are
[[paren-2-after-headword]]. No row, no `disagrees:`, no `?`.

**A word can be split mid-bracket with no `←` and no wrap warning, both halves
in the same column.** On moll-085, bracket 24 held five complete headwords,
and the last one's third sense — `3) спе-` — ran off the foot of that
bracket; the tool opened a *new* bracket, numbered 25, for the single
continuation line `лый * (о ягодах)`. There is no `←` (that marks the gutter
wrap specifically) and no `flush-wrap`/`flush-runover` warning in the context
block, because this is a plain same-column bracket boundary, not a column or
page boundary — nothing flags it. The tell is the same shape as the gutter
case: the tail bracket opens with a lowercase word-fragment, not a bold
flush-left headword. Join it into the gloss of the entry above it and give it
no row of its own. The arithmetic is easy to get backwards: five real entries
out of bracket 24 and zero out of bracket 25 nets **+3** over what a naive
"one bracket, one entry" reading of the pair would predict.

**The fault can recur three brackets running, on both columns of the same
page.** moll-099: bracket 18 opened with the *tail of the previous entry's
gloss* (no new headword) and then swallowed four full headwords with their own
glosses before the next label; two brackets later, in the other column,
labels 20 and 21 each swallowed one extra headword the same way. None of the
six missing entries were marked with `*` or anything else distinguishing them
— each was an ordinary bold flush-left word, just not given its own label.
Net effect was +5 over the context block's count (41 rows against a predicted
36), and it would have been easy to stop checking after finding the first
merged bracket. **Finding one bracket fault is a reason to check its
neighbours, not a reason to stop looking.**

The general rule it stands for belongs here though: **when something on the
page looks like damaged apparatus, check whether it is declared apparatus
first.** A mark that recurs across pages in the same position is a convention,
and this book writes its conventions down — front matter, the printed alphabet
table, the collation rule on folio 3. That is evidence and it binds. Reasoning
out what a mark "must" mean from one page is how three readers reached three
different wrong answers about the same one.
