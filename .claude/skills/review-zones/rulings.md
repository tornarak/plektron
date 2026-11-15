# Zoning the 1900 «Матеріалы»: the editor's rulings

The editor's rulings (2026-11-07) on how this book's pages are zoned, where *The
Chukchee*'s seven types did not have to answer. The types themselves are declared
in `config/zones.json`, and `harness zones bands` prints each one's description.
A ruling here is about this book, and where it and a description seem to differ,
the ruling holds.

- **Line numbers in the margin are a field of the line, never a zone.** The
  texts print 5, 10, 15 in the outer margin. The text layer reads each into its
  row, before the text on a verso and after it on a recto, and sometimes as a row
  of its own. A numbered line is judged as if the number were off it, and gives
  no evidence of an indent.
- **Each *Примѣчанія* note is one `MainZone-P`.** Its start is its printed
  opener, `N (стр. M).`, read in the text rather than off the indent: a note
  opens indented like a paragraph, and a run-on like `Сравнить №5, прим. 26.`
  returns to the margin, so the geometry cannot separate them. An indented line
  directly under the notes heading or a gap starts a note too, since a text with
  one note prints no opener (`1-200`, «Примѣчанія къ №44.»). The heading
  «Примѣчанія къ № N.» is `MainZone-Other`.
- **Parallel columns are one `MainZone-Other` band.** The book sets two versions
  of one text side by side, line against line: women's and men's pronunciation
  (nos. 25–28, 45, 46; «Въ женскомъ произношеніи» | «Въ мужскомъ
  произношеніи»), Chukchi and Russian (no. 47, the oath), and Radloff's 1861
  phrases against Bogoras's correction (no. 48). The text layer reads each row
  across both columns, so as prose the block would interleave two texts line by
  line. Splitting a row at the gutter is the OCR stage's work, not the zone's.
- **Foot matter is `QuireMarksZone`**, as in *The Chukchee*: the gathering's
  signature (`16`, `1-177`) and a chapter's folio (`I`, `1-021`), a lone number
  or numeral as the page's last line.
