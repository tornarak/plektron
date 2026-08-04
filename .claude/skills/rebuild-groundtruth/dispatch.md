# Dispatching the pass to subagents

The reading half of this pass parallelises cleanly and the adjudication half does
not. One agent per page, each stopping at a normalized `proposal.json`; the human
then reviews the pages one at a time. `2-045`/`2-046`/`2-047` were run this way,
three Sonnet readers at once.

**Hand the whole batch to one server**: `harness ocr review 2-046 2-047 --serve`.
One page on screen at a time, Done advancing to the next and stopping the server
only on the last, so the background task exiting still means the batch is finished.
A server per page put the human's half back to waiting on the tooling between
pages, which is what fanning the reading out was meant to stop. `restore` stays per
ref.

**Predict first, in the parent.** A page with nothing in `mz/ocr/` has no line
indices, so an agent sent at it has nothing to key against and will either stall or
invent a numbering. `harness ocr predict` also wants the GPU, and five agents racing
for it is slower than one loop. Survey the batch across four stores first —
`gt/zones/`, `gt/fig/`, `gt/ocr/`, `mz/ocr/` — because each answers a different
question about the dispatch:

- **`gt/zones/`** — is it a text page at all, and does it have the zones `predict`
  needs. No zones, no dispatch.
- **`gt/ocr/`** — **a page already in the ground-truth store is not a restoration
  candidate and must be dropped from the batch or dispatched knowingly.** A named
  range will contain one sooner or later: `2-031`–`2-035` contained `2-034`, one of
  the 20 pilot pages, fully keyed. Sending a reader at it puts it on the *revision*
  branch (`--store gt`, `--force` at restore), and worse, every ALTO verb it runs
  then hands it the keyed human text — so its proposal is no longer an independent
  reading and the two witnesses the span diff exists to compare have collapsed into
  one. Substitute the next page with zones and no gt, and say in the report that you
  did and why.
- **`gt/fig/`** — decides whether the agent's `ocr gaps` result means anything, and
  the *figure track is complete at 252 pages*, so absence is information rather than
  a gap in the segmentation: no figure ALTO means the page has no figures, so every
  band `gaps` reports is a genuine candidate. Where one exists the figures are
  masked and a band is meaningful too — what the agent must be told either way is
  *which* of those two situations it is in, or it will read artwork as a dropped
  line, or discount a real one as artwork.
- **`mz/ocr/`** — whether the prediction is already spent.

**Predict the batch in one process, not one call per page.** `predict` loads blla
*and* CATMuS large and initializes CUDA before it reads a line, and a shell loop over
five refs pays all of that five times: measured, 25 s for a standalone page against
~17 s each when they go through one process. Name them:

    uv run harness ocr predict 2-031 2-032 2-033 2-035 2-036

Several refs route through the sweep for exactly this reason, and they carry the
single-page override with them — a page a human ruled *not a text page* is still
predicted when you name it, and refused loudly rather than dropped in silence.

This used to want a scratch `.lst` file written only to be handed to `--itinerary`,
because the verb took one ref. `--itinerary` remains for a file-based work-list
(`gt/seg`), and it is exclusive with named refs: three ways of saying what to work
on, one per invocation.

It is on the GPU by default — `--device auto` resolves to `cuda:0` — so a slow run is
the load being paid repeatedly, not the device being wrong. Check before blaming it.

**Give each agent one ref and say so twice.** Several agents in one repo are safe
only because they touch disjoint `review/PP-NNN/` directories. The prompt names the ref
in the first line and repeats "do not touch any other page".

## What the prompt has to carry, and why each clause is there

Every item below was earned by something going wrong, in this project or in the
dispatch that produced this file.

- **Read `SKILL.md` and `keying_spec.md` in full, with Read, before anything else.**
  Say "not grep, not head" explicitly — an agent told to consult a spec will grep it
  for the term it already suspects and miss the licensing note that would have
  overridden its first guess.
- **State which branch of the loop applies.** "This page has no ground truth, so it
  is the restoration branch, `--store mz` on every ALTO verb, no `--force`." Left to
  infer, an agent reaches for the default view, and the view is the wrong witness.
- **Name the deliverable and where it stops.** "Your deliverable is
  `review/PP-NNN/proposal.json`, normalized and clean. STOP THERE." Then bar the
  rest by name: no `--serve`, no `restore`, no `gt/ocr/` write, no `views build`, no
  `--all` form of anything, no git commit. A prohibition that names the verb is
  checkable; "don't overstep" is not. `--all` is worth naming as a class now that
  every corpus-wide form is spelled that way: one flag stands between a per-page
  job and a corpus sweep, and an agent has no business on the far side of it.
- **Bar ad-hoc Python and shell listing, and list the verbs that replace them.**
  This is the clause that needed sending twice. Both readers hit permission prompts
  reaching for `ls` and `python3` — and not to edit anything, but to check that
  their own `proposal.json` existed and parsed. That case *feels* like verification
  rather than editing, so it reads as exempt from a rule written about editing.
  Say it covers existence and parse checks, and say what answers them instead:
  Glob for existence, Read for content, `proposal fix` for parse (it reads the file
  and fails loudly), `proposal codepoints` / `set` / `replace` for everything else.
- **CATMuS is not a witness to any glyph.** 0% of the inventory. Say the proposal
  must be the agent's own reading of the raster and must never be seeded from the
  machine text, or the two witnesses the span diff exists to compare collapse into
  one.
- **The zoom ceiling, numerically.** "`--zoom 2` by default, never above 4, all
  lines in one call." An agent left to its own judgement escalates, and past 4×
  there is no source detail left to buy. `--margins` is *not* a default — see the
  template; it costs a strip on every selected line and answers a question about
  the margin, which most doubts are not.
- **A settled rule is not a doubt.** Say plainly: where `keying_spec.md` states a
  closed rule, apply it and cite it; the raster is for what the spec does not
  decide. `3-063`'s reader zoomed twice to adjudicate straight-vs-curly quotes
  when §1 and §5.6 say the book sets curly throughout and never straight — the
  escaped straight quotes in the machine text were an encoding artifact the spec
  alone disposes of. That is the cheapest saving available at this rung, and it
  cuts the same way spanning does: both stop the reader paying pixels for a
  question already answered.
- **The image ladder, and that it is a ladder.** Name the three rungs in order and
  say each is paid for only where it is used. See below.
- **Superscript markers, spelled out.** `¹` U+00B9, never the ASCII digit. The error
  class with no internal signal.
- **Prefer unresolved.** "A doubt that survives one 4× look IS the answer — write it
  in `note`." Without this an agent will manufacture a disposition rather than hand
  one up.

## The failure this dispatch actually produced

Worth keeping because the prompt did not prevent it and probably cannot. `2-047`'s
reader met a raised dot in an unlicensed position, flagged it loudly and correctly —
and then keyed it **U+00B7**, calling it the "closest visual match". U+00B7 is
listed in `keying_spec.md` §2.7 as a lookalike **trap** for U+02D9: a character with
no legitimate reading anywhere in the corpus, zero-attested across `gt/ocr/`.

So the instruction to prefer "unresolved" was followed in the `note` and abandoned
in the `text`, because `text` is mandatory and something had to go in it. **An agent
that must emit a character will emit one**, and "closest visual match" is the
reasoning that produces a trap glyph. The prompt should say what to do with the
mandatory field when the identity is open: key the catalogued sort whose *letterform*
it is, and put the unlicensed environment in the `note` — never reach outside the
inventory for a shape that looks nearer.

**Check the Tier-1 dispositions in the returned report against the raster yourself.**
Not the whole page — the flagged lines, plus any claim the report makes about
corpus-wide attestation. `2-045`'s reader asserted the apostrophe/pause mark was
zero-attested and used that to license reading every raised mark as stress; the
premise held (599 U+02CA against 0 U+0027 in `gt/ocr/`) but it was a claim doing
real work in a reading, and unchecked it is a doctrine applied on faith.

## What the reading costs, and the ladder that follows from it

The reading half is dominated by images, and an image's cost is a fact about
**pixels alone**: a model sees it as 28×28 patches, `⌈w/28⌉ × ⌈h/28⌉` visual
tokens, and anything over the per-image ceiling — 2576 px long edge, 4784 tokens
— is downscaled until it fits. Greyscale, bit depth and file size do not enter
into it. Worth stating because the obvious first economy is to make the derived
images grey, and it buys **nothing** here; they already are, since `compose_sheets`
builds mode `L` and `scans/` has been greyscale since the raster pass. What that
bought was decode time.

Measured on this corpus, per page:

| image | source px | delivered | tokens |
|---|---|---|---|
| `numbered` composite | 2660×3525 | 0.64× | ~4,800 |
| one full contact sheet | 1907×1946 | 1.00× | ~4,760 |
| one `--only 10-14` sheet | 1904×517 | 1.00× | ~1,300 |
| one `zoom2` sheet | 1450×1460 | 1.00× | ~2,760 |

Two things follow, and the first is not obvious. **A whole page cannot be delivered
above about 0.64× however many pixels you send** — the ceiling does the downscaling
— so the numbered composite is a fixed ~4.8k tokens and can never settle a question
about one mark. It is an orientation instrument. But `2-031`'s three contact sheets
cost ~14.3k for the same page, and the prompt used to make reading all of them
mandatory before any zoom. Most pages of this book are English prose that never
needs a crop.

So: **`numbered` → `sheets --only` → `zoom --only`**, each rung paid for only where
it is used. An English-only page goes from ~19k tokens of mandatory images to
~4.8k. A page with four doubtful lines pays ~4.8k + ~1.3k rather than ~14.3k, and
still gets a closer look at the lines that earned one.

Two constants are tuned against that ceiling and should not be nudged without
redoing the arithmetic. `ZOOM_CLIENT_W = 1450` with `ZOOM_SHEET_H = 1600` is 3016
of the 4784 patches, so a zoom sheet is **not** resized and `--zoom N` really is
N×. And `NUMBER_FONT = 48` is large for the same reason in reverse: 0.64× of it is
the ~31 px the reader actually sees, where the contact sheets' 26 px would arrive
at 17 px and be a guess. The labels are serif rather than the sheets' mono because
at that delivered size a sans `1` is a bare stroke.

## Check the batch distributionally, before the human sees it

**Run `harness proposal marks` over every ref of the pass at once**, the moment
the subagents return:

    uv run harness proposal marks 2-031 2-032 2-033 2-035 2-036

This is the only check in the loop that needs neither a raster nor a reader's
cooperation, and it is the one that would have caught the most. Every other
safeguard here asks somebody to remember something, and the record is that they
remember it, restate it correctly, and get it wrong anyway.

It used to say "run `harness lexicon marks` and compare by eye". That verb is
corpus-wide only and groups by base letter, so it cannot express `ɪ`/`i` at all —
not a mark on a base — and the comparison was left to a human holding five pages
in their head.

**Pass every ref together, and read the rows against each other.** Most pages of
this book carry only a handful of Tier-1 terms, so one page is rarely a sample
worth a verdict; the pass pooled is. `scope: ALL` is exactly the refs you passed,
pooled, and the contrast between it and the per-ref rows is the finding:

- **one job adrift, the rest on the prior** — that reader, on that page. Re-read it.
- **every job leaning the same way, so `ALL` itself parts from `prior_pct`** —
  **systemic**. That is the dispatch prompt or the keying spec, not anyone's
  reading, and nothing else in the loop can see it. Fix the instructions before
  sending the next batch, or the next batch reproduces it.

Three arms, and only the first two are decisive. `rare` lists a form whose
character the corpus almost never sets — bare `g` at 6.1% of Tier-1 `g` — so
`2-033`'s four bare `g` would have been named without opening a scan. `conflict`
finds one word spelled two ways against the store, which is how `2-040`'s
`vaˊɪrgɪt` shows up against `2-033`'s adjudicated `vaˊɪrg̣ɪt`. `ratio` is the
weak one: it counts types rather than characters, because `2-036`'s 10% `ɪ`-share
is one word four times, and it reports a rank rather than a probability.

**Check `pages` first.** A reading degraded all the way to ASCII carries no
Tier-1 tokens, so every arm goes silent on it and the report looks clean. `types:
0` beside a page whose zones promise Tier-1 content is itself the finding.

**The two deterministic arms also run inside `harness proposal check`**, so a
reader that ran its own check should not be shipping either class. If one arrives
anyway, that is worth noting in the pass's report — it means the reader skipped
its gate, which is a different problem from misreading a glyph.

What none of it can do is decide. An outlier is a page to re-read, never a page
to correct by ratio — the number is a prompt to look, and the raster still rules.
The prior is drawn from `gt/ocr/`, whose pages were selected for Tier-1 density,
and every report says so in `prior_note`.

**And ask what the readers get wrong across passes**, which is a different
question from what this batch did:

    uv run harness ocr corrections --since <a date after the last rule change>

Unscoped it is partly archaeology — its top class is 117 straight apostrophes on
two pages keyed before a bare apostrophe became its own unconditional error. It
also undercounts by construction: a repair you make with `proposal set`/`replace`
before adjudication leaves no proposal→decision diff at all, so what it measures
is what reached the adjudicator, not what the reader wrote.

## What the 2026-08 five-page batch produced

Worth keeping because the *shape* recurred rather than the instances.

- **Dropped `g̣`, five times across three of the five readers.** One quoted §5.1's
  90% prior and named `vaˊɪrg̣ɪt` as the documented trap in the same note it keyed
  bare in, twice. Emphasis had already been tried; §5.1 now carries the contrast
  technique and the distributional check instead.
- **`ɪ` keyed as `i` or `r`, four times over two batches**, every one on a line
  whose reader reported checking it. See §5.2.
- **A note arguing against its own correct text.** `2-031` keyed its footnote
  openers correctly and attached notes claiming plain ASCII digits, citing "the
  precedent recorded for 2-034 in keying_spec.md §2.10". **The reader was not
  inventing that** — §2.10 printed `2-034`'s defective opener as a worked example,
  and a record of the error read as a statement of the convention. The section has
  been rewritten. **When a reader misapplies a rule, read the rule before
  concluding it was ignored**; the first diagnosis here was "fabricated" and it
  was wrong.
- **A reader groping through `gt/ocr/` for a convention the spec did not state**
  (the em dash in a signature line). Its answer was right and its method was not.
  keying_spec.md §2.11 now states the dash; a reader reduced to corpus archaeology
  mid-pass is a gap in the spec, and it should report one.

## What to ask for back

The page's character (kind of page, running title, folio, footnotes, figures), the
`ocr gaps` verdict *and what the agent concluded from it*, lines keyed, which lines
carry Tier-1 notation, every doubt flagged with its reason, and what the adjudicator
should look at first. Concise and concrete — the report is what you relay to the
human before handing them the URL.

## Template

**Do not transcribe this by hand — `harness ocr dispatch PP-NNN` renders it.** The
block below is the source and this section is its reasoning; the verb substitutes
the survey, and is the only thing that should ever produce a prompt from it.

That rule was written after being broken twice in one session. Hand-copying put
five clauses into the prompt an agent actually ran that existed nowhere in this
file — so the doc described a prompt nobody sent, the run measured something
unwritten, and anyone debugging the result afterwards would have debugged the wrong
text. It is the same fault as writing a glyph into a note instead of citing its
codepoint: a normative thing reproduced probabilistically, with no witness to the
difference.

The markers around the block are load-bearing (`harness/dispatch.py` reads between
them) and the `{braces}` are substituted. Everything else is sent verbatim, so
prose edited here reaches the next agent with no other step.

<!-- prompt:begin -->

    You are running the ground-truth reading pass for exactly one page of Bogoras,
    *The Chukchee*, in the repo at {root} (work in place; do not create a worktree).

    Your page ref is **{ref}**. Do not touch any other page.

    FIRST, before anything else, read these two files IN FULL with the Read tool
    (not grep, not head):
      1. .claude/skills/rebuild-groundtruth/SKILL.md — the normative pass doc
      2. keying_spec.md — the character inventory. §5's error classes are a
         per-line checklist, not background awareness.

    Then follow that skill's loop for a page that has NO ground truth (the
    "restoration" branch), which is your case: mz/ocr/chukchi-{ref}.xml already
    exists ({lines} lines over {zones} zones — `harness ocr predict` has been run
    for you). gt/ocr/chukchi-{ref}.xml does not exist.{note}

    Every ALTO verb you run must carry `--store mz`. Run commands with
    `uv run harness ...` from the repo root.

    **Your deliverable is `review/{ref}/proposal.json`, normalized and clean.
    STOP THERE.**

    Specifically, do:
      - `uv run harness ocr gaps {ref} --store mz` first. Report what it says.
        {figures} If you judge a band to be a genuinely dropped printed line,
        use `harness ocr adopt-gap` per the skill and record it in the proposal's
        `segmenter_missed` block — but that is a real judgement, so say why in
        your final report.
      - `uv run harness ocr lines {ref} --store mz` for the line indices.
      - **The image ladder. Climb it; do not start at the top.**
          1. `uv run harness ocr numbered {ref} --store mz`, then Read
             review/{ref}/numbered.png. This is the whole page with every line's
             index beside it, each line enclosed in its own ruled band. On a page
             of ordinary English prose it is the only image you need.
          2. `uv run harness ocr sheets {ref} --store mz --only <SPEC>` for the
             lines that image left in doubt, and **only** those. Give each a
             neighbour or two (`--only 10-14`, not `--only 12`) — whether a mark
             is the page's habit or this line's is a question about the lines
             around it. Do NOT sheet the whole page.
             **Name every line you mean to look at in ONE call**, as at rung 3:
             `--only 4-6,27-31,35-37,43-44`, not four calls. Sheets pack by
             height, so one call over those twelve lines is a single image where
             four calls are four — same pixels, four times the re-orientation.
             It is not a token saving and is not meant to be one; what it saves
             is images and calls.
          3. `uv run harness ocr zoom {ref} --store mz --only <SPEC>` for marks
             the sheets leave open, every such line in ONE call, `--zoom 2` by
             default. **Never above `--zoom 4`.**
             **Span the part of the line the doubt is in.** `--only` takes
             `@LO-HI`, a percentage of a line's width: a footnote opener at the
             start of its line is `42-43@0-25`, a mark two-thirds along is
             `12@55-80`. A doubt is about a *mark*, not a line — magnifying a
             whole measure renders three strips of irrelevance for one of
             evidence. Span by default; ask for a whole line only when the doubt
             really is about the whole line. A span is widened to fill the strip
             and snapped out to whitespace, so it will not cut a word — you do
             not need to pad it defensively, and a span that misses is a sign
             you did not know where the mark was, which is rung 2's job.
             **If you cannot say where in the line the mark sits, go to rung 2
             first.** Re-aiming a span three times costs more than the contact
             sheet that would have shown you where to aim once.
             Add `--margins` ONLY when the doubt is about something in the margin
             (a list number or folio the line box may exclude). It widens every
             selected line to the PrintSpace and costs an extra strip apiece. It
             is not a default and you should usually omit it.
        Say in your final report which rungs you used and which lines sent you up
        each one. If you never needed rung 2 or 3, say that too — it is a result,
        not a shortfall.
      - Author review/{ref}/proposal.json: one entry per ALTO line index, `text`
        mandatory, `resolved` spelling out codepoints for any line with notation,
        `note` for anything an adjudicator would otherwise rediscover, and a
        `contamination` block — **`blind: true` unless you can name something
        specific**, and seeing the machine text in `ocr lines` is not it (you
        cannot get the line indices without it). See SKILL.md on what that field
        was for.
      - `uv run harness proposal fix {ref}`, then re-run it without `--fix` until
        it is silent.
      - `uv run harness proposal check {ref}` — **it must exit 0**, and it is a
        different gate from `fix`: `fix` reconciles what it unambiguously can,
        `check` reports what it will not guess at, including a `resolved` field
        that disagrees with its own text. Do not report a proposal as validated
        on the strength of `fix` and `normalize` alone; a reader has already
        done that on a page this gate was failing.
      - `uv run harness corpus normalize --commit
        review/{ref}/proposal.json`, then the same command without `--commit` —
        it must exit 0.

    **Do NOT** run `harness ocr review --serve`, do NOT run `harness ocr restore`,
    do NOT write into gt/ocr/ (except via `adopt-gap`, which writes geometry
    only), do NOT run `views build`, do NOT run any `--all` form of anything —
    every verb that can sweep the corpus now says so with that flag, and none of
    them is yours — and do NOT commit anything to git. A human adjudicates your
    proposal afterwards; that step is not yours.

    **Do NOT run `harness ocr clean`.** Tidying up after yourself is the one
    prohibition here that sounds like good manners, which is why it needs
    saying. The images you opened are the only record of what you actually
    looked at: they are what an adjudicator opens to check a reading against
    the page, and what a coordinator compares against your report. Delete them
    and your account of the pass becomes its own sole witness. Cleaning is the
    coordinator's call, after the page has been adjudicated.

    Hard rules that override any instinct:
      - No ad-hoc Python and no shell listing. No `python3 -c`, no heredoc
        scripts, no hand-rolled PIL crops, and no `ls`/`cat`/`find` — **including
        merely to check that a file exists or parses.** Glob answers "does it
        exist", Read answers "what is in it", and `proposal fix` reads
        proposal.json and fails loudly on anything malformed, so running the step
        you were going to run anyway IS the parse check. Everything else is a
        verb: `proposal codepoints`, `proposal set`, `proposal replace`,
        `ocr zoom`. If you reach for a script, you are routing around a tool that
        exists.
      - Never take the CATMuS machine text in mz/ocr/ as a witness to what any
        character is, anywhere an inventory glyph could stand. It reads 0% of the
        transcription inventory, and **its errors arrive as ASCII** — it
        substitutes ' ’ / for ˊ, and i I **r** for ɪ — so "it is only wrong about
        non-ASCII" is false, and is how its `r` got keyed into a Chukchee name.
        It is evidence about line geometry and English prose, nothing else.
      - **Where keying_spec.md states a closed rule, apply it and cite it — do
        not go to the raster to confirm what the spec has already settled.** §1
        and §5.6 say the book sets curly quotes throughout and never straight
        ones, so a straight quote in the machine text is an encoding artifact,
        not a reading to adjudicate. The raster is for what the spec does not
        decide. A reader on this pass spent two whole zoom selections confirming
        exactly that; do not repeat it.
      - **A page believed to be all English is a prior, not a licence.** If a
        Tier-1 form turns up anyway it gets the full treatment — climb the
        ladder for it and key it character by character. A page believed English
        is exactly where an unmarked inventory glyph passes unread.
      - Marks that are simply present or absent — the dot under `g`, ä vs a, ɪ vs
        i vs r — often will not resolve by staring at the glyph, because the two
        sorts are the same letterform. Where the line offers a plain English
        counterpart, read the two together; that settles in seconds what a 4x
        look does not, and naming the contrast word in your note makes the
        reading checkable. Not every line offers one — this is a technique, not a
        requirement, so use it when it is there and otherwise read and flag as
        usual. What is *not* acceptable is a confident negative: keying_spec.md
        §5.1 and §5.2 record that "checked at 4x, no dot / plain i" has been
        wrong nine times across two batches, every time from a reader who
        reported having checked.
      - Read only your own page. Do not open another page's proposal.json,
        decision.json or gt/ocr/ file for evidence — a convention derived from a
        neighbouring page is what the firewall forbids, and the settled answers
        are all in keying_spec.md. If you find yourself hunting the corpus for a
        precedent, the rule is missing from the spec: say so in your report.
      - A note citing keying_spec.md should quote the sentence it relies on. Two
        readers have now cited the same section for opposite conclusions after
        reading it in full.
      - **A note may state what you saw. It may not state what another witness
        said unless you actually consulted that witness** (§5.12). Two readers in
        one batch invented a corroboration for text that was already correct —
        one claimed a letter-height measurement that does not hold, the other
        claimed CATMuS read a speck as an apostrophe when the machine text has no
        apostrophe in it. Both are one command from being checked and neither was.
        An invented second witness is worse than no note, because it is what stops
        the next reader looking.
      - **Write notes in codepoints, not glyphs** — `U+0323 COMBINING DOT BELOW`,
        not the character; describe a spacing rather than exhibiting one.
        Reproducing a glyph in prose is probabilistic the same way keying it is,
        and `corpus normalize` runs over `note` like any other field, which is
        deliberate. Do not treat that as a trap to route around.
      - **Roman numerals are plain ASCII, always** (§2.12), however small-cap they
        look. So are a bracketed chapter-opening folio (`[1]`) and the signature
        line's leading number — both are regular, both are apparatus, and neither
        is worth a zoom. Page 1 is the only slot in the book where the reading is
        even arguable, and it is a digit.
      - Before you finish, re-read every note against its own text. A note
        describing a keying decision the text does not exhibit is a defect even
        when the text is the right one — worse then, because it argues the
        adjudicator into undoing correct work.
      - Footnote and raised markers are keyed as the Unicode superscript (¹
        U+00B9 etc.), never the ASCII digit.
      - Prefer "unclear, flagged in `note`" over a confident guess. A doubt that
        survives one 4× look IS the answer — write it in `note`. **`text` is
        mandatory, and that is not licence to invent a codepoint**: if the
        identity is open, key the catalogued sort whose letterform it is and put
        the unlicensed environment in `note`. Never reach outside
        keying_spec.md's inventory for a shape that looks nearer — the lookalike
        table (§2.7) is a list of characters that are *always wrong*, and
        "closest visual match" is exactly the reasoning that lands on one.

    Final report back to me: the page's character (what kind of page it is,
    running title, folio, footnotes, figures), what `ocr gaps` said and what you
    concluded, how many lines you keyed, which lines carry Tier-1
    (Chukchee/Koryak/Yupik) notation, every doubt you flagged and why, and
    anything you want the adjudicator to look at first. Be concise and concrete.

    Then report separately on the image ladder, which is measured per run:
      - which rungs you used, and how many images you opened in total;
      - for every `ocr zoom` call, the exact `--only` spec, how many sheets it
        produced, and whether you spanned or took whole lines — and if you took
        a whole line, why the span would not have done;
      - whether the numbered page was legible enough to key English prose from
        without a contact sheet, and if not, exactly what was illegible.
      - **Name the lines you actually rendered.** A correction reported as
        confirmed on a line no image covered is the invented-second-witness
        defect (§5.12) in its cheapest form: say which lines the spec settled
        and which the raster did, and do not let one sentence cover both.

<!-- prompt:end -->
