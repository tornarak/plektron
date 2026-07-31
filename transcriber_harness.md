# Per-page OCR → TEI transcriber harness

Scope: this is the **page + OCR → TEI** pass only — it produces the base page
file (structure, foreign-span marking, uncertainty markup). It is not the
later "Annotation passes" step (persons/places/taxa, run over *finished*
TEI). Language-span marking happens here out of necessity — you can't decide
the apostrophe encoding without knowing what's Chukchi — but treat every
`xml:lang` boundary this pass draws as a fast draft for the dedicated
language-spans pass to confirm or correct, not a final answer. Nothing here
mints an authority-file id.

Chukchi ground truth does not exist yet for most of the corpus (that's the
keying pilot, still gated on spec closure). This pass runs anyway, on
whatever transcript currently exists — CATMuS draft, partially hand-corrected,
doesn't matter, treat identically. Every `<foreign>`/`<unclear>` span it
produces is provisional by construction and gets revisited once real keying
happens. That's a feature, not a gap to apologize for.

## Input contract (assembled by script, before the model ever sees the page)

Emitted as TOON (`uv run harness context PP-NNN`); `--json` gives the same
payload as indented JSON. Uniform record lists collapse to a header row plus
data rows, which is why every list below has one fixed key set.

```
page_ref: 2-176
page_image: scans/chukchi-2-176.png
catmus_draft: "<raw HTR text for this page — machine output, no authority>"

expected_folio: 538
folio_basis:
  prior_ref: 2-175
  basis_ref: 2-175
  basis_folio: 537

toc_window[3]{id,level,title,page_start,open,starts_here,distance}:
  chXVIII,1,Organization of Family and Family-Group,537,true,false,-1
  chXVIII.2,2,System of Relationship,537,true,false,-1
  chXVIII.3,2,Terms of Relationship,541,false,false,3

boundary_in: p

figures_on_page[2]{zone_id,zone_type,bbox,text}:
  eSc_textblock_78034cff,GraphicZone,...,
  eSc_textblock_d2082379,GraphicZone-FigDesc,...,Fig. 291. Wooden Amulet.

ocr_lines[3]{index,line_id,text}:
  0,eSc_line_2905eed4,VI. — HUNTING AND FISHING; WAR.
  1,eSc_line_2b719d88,SEAL-HUNTING. — The Maritime Chukchee support themselves almost
  2,eSc_line_a36bfcd9,

foreign_terms_nearby[2]{term,lang,ref}:
  Miˊrg̣ɪn,ckt,2-175
  ᴇʟɪˊhɪn,ckt,2-177

detector_flags[2]{type,line,token}:
  dot_above_g,12,ġŭmniˊn
  lexicon_miss,27,bṛothers

balance_flags[1]{type,paragraph,detail}:
  quote_balance,3,odd straight-quote count in paragraph
```

Everything here is **precomputed by deterministic script**, not derived by the
model. `toc_window` is a lookup against `data/toc.json`, each entry's `id`
copied verbatim from that table. `figures_on_page` comes from the figure track:
zone ids verbatim from the already-segmented ALTO — they are eScriptorium block
ids, `eSc_textblock_…`, never minted here — with the zone's bounding box and the
zone's text. A page contributes two kinds of zone: `GraphicZone`, which is
geometry and carries no text ever, and `GraphicZone-FigDesc`, which carries the
printed caption. The model anchors `<figure>` against a GraphicZone and never
invents a zone. `ocr_lines` is every `TextLine` from the same OCR ALTO the
`catmus_draft` above was built from, in document order, empty lines included,
each carrying its real ALTO `@ID` as `line_id`. It exists so a Tier-1 span can
optionally cite which line(s) it was read from (see the PROVENANCE section
below) — never use these ids for anything else, and never infer text from
`line_id` that isn't already visible in `catmus_draft` or the image.
`foreign_terms_nearby` is
recomputed each call from the `<foreign>` spans of committed TEI on the
physically neighbouring pages; it exists so a term keyed two ways across a
spread is *visible*, and it licenses nothing — this page's Tier-1 content comes
from this page, and a form on a neighbour is never a target to harmonize toward.
`detector_flags` are the apostrophe-adjacency, dot-above-g, word-medial-caps,
inventory-glyph and lexicon-miss checks; `balance_flags` are the paragraph-level
quote/bracket-balance checks, kept in a separate list only because they are a
different record shape. All mechanical, all run before this call. The model
never re-derives any of these; it only *uses* them. `toc_window` informs structural decisions
(headings, milestones) — it deliberately has no role in language
identification; see the language-spans section below for why.

**Pages are addressed by `PP-NNN` ref — part, and scan index within that
part — and by nothing else.** NNN is a *scan index*, not a printed folio: part 1
runs 001–362, part 2 001–268, part 3 001–202, while the printed folio runs
continuously 1–732 across the volume with plates and front matter unpaginated.
Neither is derivable from the other. A bare integer names no page, and the CLI
rejects one rather than guessing which part was meant.

**`expected_folio` is an expectation, not an instruction — and often null.**
The printed folio is not derivable from the scan index, so it is known only
where a transcribed page recorded one: the prediction is the last *numbered*
preceding page's folio plus one, and it is `null` wherever that chain breaks (an
untranscribed predecessor, the first scan of a part). Null is not a defect. It
means read the folio off the image and do not guess — which is what the model
does in either case (see PAGE FURNITURE below); the prediction exists so that a
drift surfaces as a warning instead of propagating silently. Where the two
disagree, the folio on the page wins and the mismatch gets a comment.

**`toc_window` is a neighbourhood, not a resolution.** It carries the ToC
entries near the expected folio *plus* any the milestone fold believes open,
each marked `open` / `starts_here` / `distance` rather than filtered down to an
answer. The marks are derived from a prediction and inherit its errors, so they
inform a decision made against the page; they do not make it. A believed-open
entry far from the window still appears, because that distance is exactly the
discrepancy worth seeing. With `expected_folio` null the window thins to the
believed-open set alone, and nothing downstream treats absence from it as
evidence.

**`boundary_in`** is the seam record for the gap *before* this page — see the
continuation patch step below. It is supplied for orientation only; this call
never acts on it.

**Continuation markup is not part of this call at all.** It's 100%
geometry-derived (see below) and never depends on anything the model would
read from the text, so there's nothing for the model to decide here — asking
it to would just be a second, redundant place for the same fact to go wrong.
The model emits elements for whatever breaks are visible *within* the page
and never writes `@part`, `@prev`, or `@next`. A separate deterministic pass,
run once two-page geometry exists, patches these onto the first/last relevant
element of each file.

**The continuation patch step**, run outside this harness entirely:

- One canonical table, `boundaries.json`, keyed by `PP-NNN` ref (never by
  folio — the folio is not known script-side, and is not even defined for
  plates): one record per inter-page gap,
  `{"open": "p" | "quote" | "table" | "note" | null}`,
  where the value names the element left open across the gap immediately
  following that ref (`null` = clean break, *absent* = not yet computed, which
  is a different thing). Computed once from ALTO
  line/baseline geometry — a page's last line running short of the column
  width vs. the next scan's first line carrying a left-indent relative to the
  body baseline, plus footnote-zone geometry for note run-over (see the
  sequencing note below for why both ends are needed). One value per gap,
  never duplicated per page. "Next" means the next *scan* in the same part;
  gaps do not cross a part boundary, and the last scan of a part has no record.
- Patch logic, per ref R, using `boundary[prev(R)]` (call it `start`) and
  `boundary[R]` (call it `end`), where `prev(R)` is the preceding scan in the
  same part:
  - **Fragmentable elements** (`p`, `quote` — both members of TEI
    `att.fragmentable`) receive `@part`:

    | start | end | first element | last element |
    |---|---|---|---|
    | null | null | no `@part` | no `@part` |
    | open | null | `part="F"` | (same element if the page has one) |
    | null | open | `part="I"` | (same element if the page has one) |
    | open | open | `part="M"` | (same element if the page has one) |

    If the page's first and last such element differ, only the first gets
    `start`'s value and only the last gets `end`'s value; everything between
    is page-internal and never gets `@part`.
  - **Non-fragmentable elements** (`table`, `note` — TEI provides no `@part`
    for these) are instead linked: the fragment on ref R gets
    `next="#..."`, the fragment on the next scan gets `prev="#..."`, with
    `xml:id`s minted deterministically by the patch pass from the **ref**, not
    the folio (`tbl-{PP-NNN}-{i}`, `note-{PP-NNN}-{n}`) — every scan has a ref,
    and a plate has no folio to mint from. The per-page model never mints
    these ids.
- `boundary[R]` is *absent*-as-unknown until the following scan is segmented;
  it is never written as `null` to mean "don't know", since `null` is the clean
  break. Patch step re-runs whenever new boundary values land — a page's file
  may go out once unpatched and get amended later. That's expected, not a bug; it's why this
  lives outside the per-page LLM call instead of blocking on it.

**Why the boundary check needs both pages, not one.** Text content doesn't
work at all — a paragraph resuming mid-flow across a page break routinely
lands on a sentence boundary too, so a continuation page opens capitalized
just like a fresh paragraph would. The real signal is layout, and even that
needs both ends: page N's last line running short of the column width is a
fairly reliable paragraph-end signal alone, but fails on the paragraph that
happens to end near the margin; page N+1's first line carrying a left-indent
is a fairly reliable new-paragraph signal alone, but fails wherever indent
gets lost in segmentation. Checking both catches what either one misses on
its own.

## Output contract

One TEI page file, matching the established per-page template: `<pb>` first,
no `<div>`, minimal `teiHeader` (page number only, everything else "see
corpus teiHeader"), footnotes anchored at the marker, figures anchored at
first reference against `figures_on_page` zones. No `<lb/>` anywhere — the
line-level record lives in the ALTO, which is committed alongside; the TEI
carries the reading text.

Determinism footnote: comments referencing `foreign_terms_nearby` variants make
regeneration of page N sensitive to pages transcribed after N's first run —
the field is recomputed from committed TEI every call, so it grows as
neighbours land. That's formally within "byte-identical on unchanged *input*"
— the input changed — but worth stating so nobody mistakes it for the
regression harness failing.

---

## The prompt

```
You are producing one TEI page file from a CATMuS draft transcript and the
page image it was drawn from. Read them together — the draft is a starting
point, not a source of truth on its own.

PAGE FURNITURE AND THE FOLIO
- The printed folio is content: transcribe it into <pb n="{printed folio}"/>,
  the first element in <body>. Read it off the image — never copy
  `expected_folio` into `n=` because it was supplied. It is a prediction from
  the preceding page, it is null on any page whose predecessor isn't
  transcribed, and it is the thing your folio is *checked against*, not the
  thing it is copied from. This <pb> is what the seam ledger folds forward to
  predict the next page, so a folio invented here is a folio the rest of the
  volume inherits.
- **Folio printed on the page.** Transcribe it. If it disagrees with a non-null
  `expected_folio`, the printed folio wins; add immediately after <pb>:
  <!-- printed folio {folio} disagrees with expected {expected_folio}
  (predicted from {basis_ref}): check ToC alignment -->. With `expected_folio`
  null there is nothing to disagree with and no comment is needed — the normal
  case on a page whose predecessor isn't transcribed.
- **No folio printed on the page** (plates, some chapter openings, blanks).
  Emit <pb/> with no n=, plus <!-- no printed folio on this page -->. This is a
  positive assertion — nothing was printed here — and the ledger reads it as
  one: an unpaginated page doesn't advance the printed count, so the next page
  is predicted from the last numbered one rather than from this.
- A folio that is *present but unreadable* (damage, crop) is neither of the
  above, and on these scans should be vanishingly rare — if you hit one, don't
  encode it as <pb/>, which would assert the page was never numbered. Comment
  and ask. Nothing cascades either way: the next page with a legible folio
  re-anchors the prediction, so the cost of getting this wrong is one spurious
  mismatch warning, not a drifting volume.
- Running heads and series titles ("BOGORAS. THE CHUKCHEE.", "JESUP NORTH
  PACIFIC EXPEDITION, VOL. VII.") are discarded silently — not <fw>, not a
  comment, nothing. They are identifiable by position (topmost line) and by
  their fixed, textually redundant content; they never contain chapter
  titles and must never reach the heading logic below.

STRUCTURE (mechanical — use the supplied values, do not re-derive them)
- Wrap the page's prose in <p>, one per visible paragraph break on this page
  (blank line or first-line indent in the draft/image). Do not write @part,
  @prev, @next, or any xml:id on any element, ever — page-boundary
  continuation (for paragraphs, block quotes, tables, and footnotes alike)
  is resolved entirely by a separate deterministic pass after this one,
  using geometry this call does not have access to. If you find yourself
  wanting to mark something as continuing or not-yet-finished, don't; just
  emit the element and move on.
- teiHeader: use this template exactly, changing only the page number (the
  printed folio, per above; omitted where the page has none — then the
  sourceDesc reads "see corpus teiHeader" alone).

      <teiHeader>
        <fileDesc>
          <titleStmt>
            <title>see corpus teiHeader</title>
          </titleStmt>
          <publicationStmt>
            <p>see corpus teiHeader</p>
          </publicationStmt>
          <sourceDesc>
            <p>see corpus teiHeader; page {folio}</p>
          </sourceDesc>
        </fileDesc>
      </teiHeader>

  **No `respStmt` here.** The provenance ranks that `@resp` points at are
  declared once, in the corpus teiHeader, and never repeated per page. `@resp`
  is a URI reference resolved against the document being processed, and a page
  file is a fragment rather than a standalone document — it already defers
  title, publication and source the same way. So `resp="#llm"` on this page is
  a dangling pointer read alone and a resolving one read as assembled, which is
  true of the whole header and is not a defect to fix here. One declaration
  cannot drift from itself; 730 copies can.

HEADINGS — milestone vs. local caption, fully specified
- The model does not construct milestone content. If the body contains
  heading-shaped text (isolated line, capitalized or small-capped, no
  terminal punctuation) that matches an entry in `toc_window`, emit exactly:

      <milestone unit="{unit}" n="{id}"/>

  where {id} is copied verbatim from that entry's `id` field (never the
  title, never a number you construct) and {unit} is fixed by that entry's
  `level`:

  | level | unit |
  |---|---|
  | 1 | chapter |
  | 2 | section |
  | 3 | subsection |
  | 4 | subsubsection |

  (level 0 — front matter — never produces a milestone; those pages have no
  chapter to open.) Nothing else goes on this element. No title text, no
  page attribute, no comment, unless a fallback case below says otherwise.

  **The match is to the text on the page, not to the marks.** `starts_here`
  and `open` are predictions keyed to a predicted folio; they tell you which
  entry to look at first, and they are wrong often enough that they may never
  be the reason a milestone is or isn't emitted. Heading-shaped text matching a
  window entry marked `starts_here: false` is still that milestone — the folio
  prediction was off, and the mismatch warning is the right place for that to
  surface. Where `expected_folio` is null there are no `starts_here` marks at
  all and the window is thin; match against what it does contain, and if the
  heading on the page matches nothing in it, take the no-ToC-match branch below
  rather than reaching past the window for a better fit.
- If heading-shaped text does NOT match anything in `toc_window` (a table
  caption, a list label, a run-in like "Consanguinity"): it is NOT a
  milestone.
  - If it's immediately followed by a <list> or <table>, attach it as that
    element's <head> child, copying the heading text exactly as it appears
    in the draft — no correction, no retitling.
  - If it isn't followed by either (labels something else, or nothing
    structured), do not invent a home for it. Leave it as plain text where
    it sits and add an XML comment immediately after it:
    <!-- heading-shaped text, no ToC match, no list/table follows: needs a
    human call on where this attaches --> — and stop there. Never force a
    <head> onto something it doesn't caption.
  Never let a non-ToC heading enter chapter/section state under any
  circumstance.
- If an entry is marked `starts_here: true` but nothing in the body matches it,
  do not force a milestone. Add a comment instead:
  <!-- expected milestone for {id} ({title}) not found on this page: check
  for a missed milestone or a heading straddling the page boundary -->,
  using the id/title from the unmatched entry verbatim. A `starts_here` that
  finds nothing is as likely to mean the folio prediction is off by one as it
  is to mean a heading was missed; the comment says so and leaves it open.

FOOTNOTES
- <note> gets n="{marker}" where {marker} is the exact number/symbol printed
  at the footnote marker (an integer in this book) — copy it, don't
  renumber, don't infer it from position in a list of footnotes.
- Anchor every <note> at its exact marker position in the running text — not
  gathered at the page foot, not moved to the nearest paragraph or sentence
  boundary. If the marker falls inside a parenthetical or mid-clause, the
  <note> goes exactly there, even if that's awkward XML nesting.
- place="bottom" on every note (presentational fact about this printing, not
  a structural claim).
- Orphan foot-text: if the footnote zone contains text with no marker
  anchoring it on this page (a note run over from the previous page), emit
  it as a <note> with NO n= attribute, placed after the last <p>, preceded
  by exactly: <!-- footnote continuation, no marker on this page: linking
  resolved by the continuation patch pass -->. Do not guess which note it
  continues.

FIGURES
- Anchor <figure> at the first textual reference to it ("Fig. 291", "see
  figure on p. ..."), pointing at the matching zone_id from
  figures_on_page via facs="#{zone_id}". Match reference to zone by figure
  number against the supplied loi_caption. Never invent a zone_id; if a
  textual reference matches nothing in figures_on_page, or a supplied zone
  is never referenced on this page, add a comment naming the orphan and
  emit nothing else for it.

CONTENT SHAPE — prose vs. gloss-list vs. table, fully specified, not left to
feel
- Default is <p>. Use it unless one of the two patterns below applies.
- <list type="gloss"> when the body is formatted as a run of entries each
  shaped [term] [dot leaders] [short English gloss] — this book's dictionary-
  style vocabulary tables (the Consanguinity list on p. 538 is the reference
  case). One <item> per entry, containing <term xml:lang="..."> (language per
  the Tier 1/Tier 2 rules below, from the adjacent English, never from what
  section the list is in) or plain text if the term is English, followed by
  <gloss>. An entry indented
  further right than its neighbors is a sub-entry: nest it in its own
  <list type="gloss"> inside the parent <item>, matching the indent exactly
  — one nesting level per visible indent level, never flattened, never
  invented.
- <table> only for genuine multi-column tabular data with column headers
  (numeric tables, comparative charts) — not for the leader-dot term/gloss
  pattern above, which is <list type="gloss"> even though it visually uses
  dot leaders like a table of contents does.
- If a page's content shape doesn't cleanly match either pattern, default to
  <p> and add a comment flagging the ambiguity rather than forcing a <list>
  or <table> structure onto it.

LANGUAGE SPANS AND THE FIREWALL — read this twice
- Non-English content splits into two tiers, treated differently, because the
  actual risk differs by language, not just by "is it English":

  TIER 1 — Americanist-apparatus languages. Same firewall as Chukchi, because
  it IS Chukchi's firewall: these are transcribed in the same ambiguous
  phonetic notation this whole project exists to protect. Closed set:
    - "ckt" — Chukchi. Default. Use this unless the English text
      *immediately surrounding the span* explicitly names it otherwise —
      not the chapter, not the section, the actual sentence the form sits
      in ("...belongs rather to the Koryak language", "the Eskimo word
      for...").
    - "kpy" — Koryak. Only when the adjacent English names "Koryak"
      specifically.
    - "ypk" — Eskimo/Yupik. Only when the adjacent English names "Eskimo"
      or "Yupik". This is the only code for this family in the set — the
      book does not distinguish Naukan from Central Siberian Yupik (or any
      other Yupik variety) anywhere it's been checked so far, and inventing
      that distinction because ISO 639-3 happens to offer "ess" and "ynk"
      would be assuming precision the source doesn't carry. If a future
      page does name a specific Yupik variety explicitly, that's new
      evidence and worth revisiting the set then — not something to
      pre-empt now on the strength of a code existing.

  There is no section- or chapter-level signal for any of this. A comparative
  citation in another language can appear anywhere the author finds it
  useful, regardless of what the page's heading says — the Koryak gloss for
  "grandmother" on p. 538 sits inside "System of Relationship," nowhere near
  anything labeled Koryak, which is the concrete case in hand for why
  position-based hints don't work: the signal was in the sentence itself
  ("belongs rather to the Koryak language"), not in where the sentence
  happened to fall. Do not weight the default by chapter or section content
  at all. If the immediate sentence doesn't name a language, the span is
  "ckt" — full stop, not a leaning, not adjusted by what section this is.
  If you're genuinely unsure even after reading the local sentence, that's
  an <unclear> case, not a guessing-with-more-steps case.

  TIER 2 — standard European languages (Russian, Latin, French, and others as
  they turn up: German is likely given citations elsewhere in this project's
  apparatus, though not yet confirmed to appear in the book itself). Use the
  ordinary code for whatever you recognize with normal confidence — "ru",
  "la", "fr", "de", etc. This tier is NOT closed the way Tier 1 is: these
  orthographies aren't ambiguous the way Americanist notation is (Russian's
  script alone rules out any confusion with Chukchi transcription), so
  misidentifying French as Latin, or missing a Russian loanword, is a
  low-consequence error, not a firewall breach.
- TIER 2 CORRECTION AUTHORITY. Fidelity matters only for idiosyncratic
  transcription of languages the model doesn't know; Tier 2 is by
  definition languages it does. Accordingly:
  - Confirmed OCR slips in Tier-2 text are corrected under the same rules
    as English prose below (image-confirmed, reading not in doubt).
  - Russian specifically carries a MODERNIZATION LICENSE. The book is
    1904–1909, so ALL of its Russian is pre-1918 orthography; you may
    lossily replace it with post-reform spelling PROVIDED (a) the word is
    glossed or its sense is otherwise explicit in the surrounding English,
    and (b) you are certain of the meaning. Most instances are trivial
    ethnonyms and realia — "chukcha", "nerpa" — where this is safe. If
    either condition fails, reproduce what is printed and move on;
    unmodernized Russian is not an error and needs no flag.

    The closed list of what you will meet, because you cannot decide to
    modernize a character you did not notice (keying spec §2.7 has the
    confusability notes):

      і U+0456 -> и      decimal i; before a vowel or й (Россія)
      ѣ U+0463 -> е      yat; frequent — хлѣбъ, бѣлый, дѣло
      ѳ U+0473 -> ф      fita; Greek loans only — ариѳметика
      ѵ U+0475 -> и      izhitsa; church-Greek only, very rare — мѵро
      ъ U+044A -> ---    hard sign, WORD-FINAL ONLY (лахтакъ -> лахтак)

    Uppercase forms are U+0406 U+0462 U+0472 U+0474 U+042A. The hard sign
    is the one to be careful with: U+044A is live modern Russian as a
    separator (объект), so only its word-final position is pre-reform and
    only that position is dropped.

    Three of these are CROSS-SCRIPT LOOKALIKES — і against Latin `i`, ѵ
    against Latin `v`, ѳ against `o` — and і/`i` are the same letterform in
    a serif face. Inside a Cyrillic word the Cyrillic codepoint is always
    the right answer; a Latin letter mixed into Cyrillic is a defect no
    grep here catches, since the lookalike census is scoped to Tier-1.

    The draft cannot help you with any of this: CATMuS lost every one of
    the 29 Cyrillic characters on the one page where this was measured, so
    Russian is read off the image exactly as the Tier-1 forms are, even
    though it carries no `@resp`. What Russian does have that Tier-1 lacks
    is a competent reader downstream and a dictionary — which is why the
    license exists at all, and why it stops at "certain of the meaning".
  - Latin stays as printed: era-standard usage and the author's own
    idiosyncrasies are not mistakes. Latin excerpts translating brief
    passages are very likely doing the era-standard job of moving explicit
    material out of English for propriety — expect this especially around
    ch. XV (Sexual Perversion and Transformed Shamans, p. 448). Being in
    Latin there is the author's choice, not a transcription problem:
    preserve it exactly, don't translate it, don't flag it as if something
    were wrong.
- THE FIREWALL, restated wide: inside ANY element bearing a Tier-1 xml:lang
  ("ckt", "kpy", "ypk") — <foreign>, <term>, <unclear>, anything a later
  pass wraps a form in — what you emit is a PROPOSAL and is marked as one.
  It is never an adopted glyph identity, no matter how confident the reading
  or how clean the image.

  "Proposal" describes its AUTHORITY, not the care owed to it. It is not a
  licence to guess, to approximate, or to leave a mark for someone else to
  catch. The standard is every mark on the form read and accounted for,
  character by character, at magnification where the letterform is small or
  the mark sits under a descender.

  There IS a repair pass — that is what marking the span `#llm` is for, since
  a query over the corpus returns precisely the forms awaiting a human. But it
  finds the span, not the error. Repair is one editor back at the raster with
  no second witness available: the recognizer reads none of this notation,
  there is no dictionary and no fluent reader to check a Chukchee form
  against. So the pass is single-witness, paid for in the scarcest resource
  on the project, and every avoidable slip is a line of it spent for nothing.

  The slips that survive it are the ones with no internal signal. A dropped
  mark inside an otherwise plausible form reads as correct in the TEI, so
  nothing draws the eye to it. `1-074` is the measurement: two dropped U+0323
  under a `g`, both missed by the reader's own second look, both caught only by
  the editor at the page. Where you cannot settle a letterform, <unclear> is
  the answer; the likelier form is never the answer.

  The firewall is a rule about HIERARCHIES OF PROVENANCE, not about matching
  an upstream file. It used to be stated as "reproduce the draft's characters
  exactly", and that was wrong in a way worth knowing, because it will read
  as the safe formulation: `catmus_draft` is stock CATMuS, which produces
  ZERO inventory glyphs (measured against a human key — 0% of the inventory,
  all of U+02CA, ɪ and ᵋ lost, all Cyrillic lost). Obeying the old rule
  literally meant emitting Tier-1 spans you could see were wrong, and the
  validator's substring check enforced it; both are gone. The draft is a
  witness to line geometry and to English, and to nothing else.

  PROVENANCE IS AN ATTRIBUTE, and it is not optional. Every element bearing a
  Tier-1 xml:lang carries `@resp`, pointing at a rank declared once in the
  corpus teiHeader — never in the page file, see the teiHeader item above.
  Three ranks, strictly ordered:

  | @resp   | rank | meaning | who may create it |
  |---|---|---|---|
  | `#ed`   | ratified | a human keyed or confirmed this span against the page; an ADOPTED glyph identity | a human, by an explicit act |
  | `#llm`  | proposed | a model read this span off the page image; a reading, not an identity | this pass |
  | `#htr`  | unexamined | recognizer output nobody has looked at | the import that made the draft |

  YOU EMIT `resp="#llm"`. Always, on every Tier-1 element, including
  <unclear>, including a span you consider beyond doubt, including a bare
  ASCII form with no inventory glyph in it at all. You never emit `#ed` and
  you never emit `#htr`. Emitting `#ed` is precisely the promotion this
  firewall exists to prevent, and it is the one breach that is mechanically
  detectable rather than a matter of judgment — so the gate detects it, and
  a Tier-1 element with no `@resp` at all is an ERROR too. Absent provenance
  is not a small omission: to anything downstream that does not check, an
  unmarked span is indistinguishable from a ratified one, which is the
  fluent-nonsense failure with the error signal filed off.

  Rank only ever rises by a human act. Nothing this pass does, and no amount
  of downstream processing, moves `#llm` to `#ed`.

  `@resp` and <unclear> are orthogonal and answer different questions.
  `@resp` says WHO READ IT; <unclear> says WHETHER THE IMAGE DECIDED. So
  `<unclear xml:lang="ckt" resp="#llm" reason="...">` is the ordinary case for
  an ambiguous letterform, and a confident reading is still `resp="#llm"`
  without <unclear>. Confidence is not authority.

  USE `@facs` TO FLAG A SPAN WORTH A SECOND LOOK. Set it on any Tier-1
  element whose reading took real deliberation — a hard letterform, a mark
  you went back to the image to settle, a form you'd want re-checked before
  it's ratified — and point it at the `line_id`(s) in `ocr_lines` you actually
  read from: `facs="#eSc_line_e5fa4af8"`, or `facs="#id1 #id2"` for a reading
  you checked against how the same mark prints on a neighbouring line (not for
  a form split across a line break, which essentially never happens here, see
  keying_spec.md §2.1 on the connector hyphen). It's what turns a flagged span
  into a one-command raster lookup for whoever reviews it next:
  `harness zoom PP-NNN --only <index> --from gt/ocr` (the `--from` matters —
  `zoom`'s default store is a different ALTO than the one these ids come
  from). Reserve it for the spans that actually earned it, the same judgment
  call as leaving a comment — a `@facs` on every span stops meaning anything.
  It's a pointer, not a rank: it never substitutes for `@resp`, and citing a
  line doesn't make a reading any more authoritative than an uncited one.
  Never invent a `line_id`; omit `@facs` rather than guess.

  Tier-2 spans (ru, la, de, …) do not require `@resp`. The asymmetry is the
  point of calling this a hierarchy: a misread Russian or Latin word is an
  ordinary error that any reader of the language catches, whereas a misread
  Chukchee form is unfalsifiable — there is no competent reader and no
  dictionary to check it against, which is why this project exists.

  What the rule forbids, and still does:
    - PROMOTION. A reading of yours may not be presented as ratified, and
      nothing downstream may treat it as one. Rank is carried by the span's
      provenance, and provenance only ever moves up by a human act.
    - ORIGINATION by inference. You do not derive a glyph from what the
      notation "should" contain, from a form on an adjacent page, from
      `foreign_terms_nearby`, or from any pattern across the corpus. Only the
      image in front of you, plus book-internal apparatus (the p. 10 key, the
      List of Illustrations, the printed ToC) which IS evidence and binds.
    - NORMALIZATION. You do not correct a Tier-1 spelling, regularize a mark,
      fix what looks like a typo, or harmonize a variant.
      `foreign_terms_nearby` is read-only reference for spotting POSSIBLE
      variants to flag. If you notice one, note it in a comment.
  So: read the form character by character off the image, key exactly what is
  there, mark it unratified — and where the letterform genuinely does not
  decide, say so with <unclear> instead of choosing the likelier form.
- SMALL CAPS, two regimes. Inside Tier-1 spans, ᴀ ᴇ ɪ ʟ are CHARACTERS of
  the notation (the schwa class and a lateral sort), reproduced at their
  codepoints, never case-folded, never rendered as <hi> — the
  word-medial-caps detector is the alarm at exactly this boundary. In
  English prose, small caps are rendition only: normalize silently to
  ordinary case, or use <hi rend="smallcaps"> where the emphasis is
  evidently deliberate (e.g. lettered like a proper heading treatment).
  Never let the English regime leak into a Tier-1 span or vice versa.
- HYPHENS, two regimes. In English and Tier-2 text, a line-end hyphen is a
  printing artifact: join the word and discard the hyphen, silently — no
  <lb/>, no comment. (Retain a hyphen only when it is evidently lexical —
  a compound that also appears hyphenated mid-line.) Inside Tier-1 spans,
  the hyphen is a SORT (U+002D, the connector) and forms essentially never
  break across lines: never join, never discard. A line-end hyphen inside
  a Tier-1 span is an anomaly — reproduce the draft as-is and add a
  comment flagging it for a human join decision.
- CODEPOINT HYGIENE, two scopes. In English and Tier-2 prose, REPRODUCE THE
  PRINT, curly quotes included. The book sets them; nothing about an
  apostrophe in English prose is load-bearing, so there is no conflation
  hazard to protect against and normalizing would discard a real feature of
  the setting. (This is a change: the policy was corpus-wide ASCII and is now
  scoped — keying spec §1, rev 2.3. The gate agrees: `FORBIDDEN_PROSE` no
  longer contains the four curly quotes.) What stays forbidden in prose is
  the set with no legitimate English use at all — U+00B4, U+02BC, U+02BB,
  U+2010.
  ONE BOUNDED EXCEPTION to reproducing the print: the book sets FRENCH
  SPACING, a thin space before `;` and `:` (`purpose ; but`). Key ENGLISH
  SPACING — `purpose; but`, no space (keying spec §2.9, editor's ruling). It is
  the only such override, and it is narrow: a thin space before punctuation has
  no lexical content and would put a space inside a token for every tokenizer
  downstream, whereas a curly quote carries a distinction the notation uses.
  This licenses nothing else about spacing. An interword space that is present
  is keyed; `i. e.,` keeps its space and never closes up to `i.e.,`.
  Inside Tier-1 spans, U+0027 and U+002D are the only apostrophe and hyphen,
  because there U+0027 IS the spirant and pause mark. A curly quote inside a
  Tier-1 span is a lookalike and lands in the WORKLIST for a human ruling —
  do not resolve it yourself, and equally do not import one from the draft.
- Where your reading of the image does not decide a Tier-1 character, wrap it
  in <unclear reason="...">, describing in plain terms what is ambiguous
  (e.g., "breve or caron; i loses its dot under an above-mark") without
  asserting which reading is correct. That is the honest output for an
  ambiguous letterform, and it is what a later human pass adjudicates.
  A disagreement with `catmus_draft` is NOT by itself a reason for <unclear>
  — the draft has no vote on any non-ASCII character, so disagreement there
  is the expected case rather than a signal. A detector_flags entry
  overlapping a Tier-1 span is likewise information, not a verdict.
- No exception for confidence level, in either direction. Being sure does not
  let you present a reading as ratified; being unsure does not let you pick
  the plausible form and move on.

ENGLISH PROSE — where fixing is licensed
- Confirmed OCR slips in ordinary English text may be corrected directly, no
  <unclear> needed, PROVIDED: (a) the fix is confirmed against the page
  image, not just inferred from the draft looking wrong, and (b) the
  corrected reading is not itself in doubt. "bṛothers" → "brothers" (a
  diacritic contaminated a plain English word) is this kind of fix.
  "Melder brother" → "elder brother" (confirmed against the image) is this
  kind of fix.
- A dropped quote or bracket flagged by balance_flags may be restored ONLY
  if the page image confirms it — never inferred purely from the parity
  check. The parity check tells you where to look, not what was there.
- If you cannot confirm the correct reading against the image, leave the
  draft as-is and flag it in a comment. Do not guess at English text any
  more than you'd guess at Chukchi.

SELF-CHECK BEFORE EMITTING
- Is <pb n=> the printed folio as it appears on the page, checked against
  expected_folio where that is non-null, with a comment on mismatch? If the
  page carries no printed folio, is it <pb/> with no n=?
- Did any running head or series title survive into the output? (Should
  always be no — discarded silently, never fed to heading logic.)
- Did I write @part, @prev, @next, or an xml:id anywhere? (Should always be
  no — continuation is not this pass's job.)
- Did I modify a single character inside any element bearing a Tier-1
  xml:lang? Case-fold a small cap there? Join or discard a hyphen there?
  (All: should always be no.)
- Is every apostrophe and quotation mark in English/Tier-2 prose ASCII
  (U+0027 / U+0022)?
- Every Russian modernization: was the word glossed or its sense explicit,
  and the meaning certain? If either was doubtful, did it stay verbatim?
- Every <milestone>: is its n= copied verbatim from a toc_window id, with no
  title text, invented number, or extra attribute anywhere on the element?
- Every Tier 1 xml:lang value ("ckt"/"kpy"/"ypk"): is it "ckt" unless the
  *immediate sentence* names Koryak or Eskimo/Yupik specifically? No use of
  chapter/section context, no "ess"/"ynk" precision the source doesn't
  support?
- Does every heading-shaped run in the body end up as one of: a <milestone>
  matched to toc_window, a <head> attached to a local list/table, or an
  explicit unresolved-comment — never left bare, never silently dropped?
- Is every footnote anchored at its marker, not gathered at the foot — and
  every orphan foot-text a <note> without n= plus the fixed comment?
- Does every <figure> point at a supplied zone_id, with orphans (either
  direction) commented rather than invented?
- Does every Tier-1 @facs, where present, point at a real line_id from
  ocr_lines — and is it present only on spans that actually warranted a
  closer look, not blanket-applied?
- For every detector_flags entry: did I either confirm-and-fix against the
  image, or leave it untouched and note why?
- Is there any <lb/> anywhere? (Should always be no.)
- Would running this exact prompt again on the same input produce a
  byte-identical file?
```

---

## What this deliberately does not do

- **Does not resolve open F-numbered flags** from the keying-spec residue
  (F4 lateral/rhotic sorts, F10, etc.). Those are corpus-wide policy
  questions, not per-page judgment calls — a per-page pass resolving them
  independently would produce 730 inconsistent answers.
- **Does not produce figure zones.** GraphicZone/FigDesc handling is a
  separate headless pipeline; this pass only anchors `<figure>` at first
  textual reference, pointing at zones that pipeline already produced and
  the script supplied in `figures_on_page`.
- **Does not mint entity ids** — persons, places, taxa are later passes,
  over finished TEI — **nor structural xml:ids**: the continuation patch
  pass mints those, deterministically.
- **Does not require Chukchi ground truth to exist.** Runs on whatever draft
  is current; output is expected to be patched once real keying lands.
- **`@facs` review is a separate, later pass.** This pass proposes the
  pointer; resolving it into a crop and acting on what's found is someone
  else's next step.
