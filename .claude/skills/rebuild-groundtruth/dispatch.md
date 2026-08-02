# Dispatching the pass to subagents

The reading half of this pass parallelises cleanly and the adjudication half does
not. One agent per page, each stopping at a normalized `proposal.json`; the human
then reviews the pages one at a time. `2-045`/`2-046`/`2-047` were run this way,
three Sonnet readers at once.

**Predict first, in the parent.** A page with nothing in `mz/ocr/` has no line
indices, so an agent sent at it has nothing to key against and will either stall or
invent a numbering. `harness ocr predict` also wants the GPU, and three agents
racing for it is slower than one loop. Check the pages are text pages with zones
before spending the prediction:

    ls gt/zones/chukchi-PP-NNN.xml gt/fig/chukchi-PP-NNN.xml
    uv run harness ocr predict PP-NNN

`gt/fig/` is what decides whether the agent's `ocr gaps` result means anything: with
no figure ALTO the page reports its own artwork as uncovered ink, and the agent has
to be told so or it will read a false positive as a dropped line.

**Give each agent one ref and say so twice.** Three agents in one repo is safe only
because they touch disjoint `review/PP-NNN/` directories. The prompt names the ref
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
  bare `corpus normalize`, no git commit. A prohibition that names the verb is
  checkable; "don't overstep" is not.
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
  lines in one call, use `--margins`." An agent left to its own judgement escalates,
  and past 4× there is no source detail left to buy.
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

## What to ask for back

The page's character (kind of page, running title, folio, footnotes, figures), the
`ocr gaps` verdict *and what the agent concluded from it*, lines keyed, which lines
carry Tier-1 notation, every doubt flagged with its reason, and what the adjudicator
should look at first. Concise and concrete — the report is what you relay to the
human before handing them the URL.

## Template

Substitute the ref, the line/zone counts from `predict`, and any page-specific note
(`2-047` got "19 lines over 5 zones suggests a sparse or figure-heavy page, so the
gap check matters more than usual here").

    You are running the ground-truth reading pass for exactly one page of Bogoras,
    *The Chukchee*, in the repo at <ROOT> (work in place; do not create a worktree).

    Your page ref is **PP-NNN**. Do not touch any other page.

    FIRST, before anything else, read these two files IN FULL with the Read tool
    (not grep, not head):
      1. .claude/skills/rebuild-groundtruth/SKILL.md — the normative pass doc
      2. keying_spec.md — the character inventory. §5's error classes are a
         per-line checklist, not background awareness.

    Then follow that skill's loop for a page that has NO ground truth (the
    "restoration" branch), which is your case: mz/ocr/chukchi-PP-NNN.xml already
    exists (N lines, M zones — `harness ocr predict` has been run for you).
    gt/ocr/chukchi-PP-NNN.xml does not exist.

    Every ALTO verb you run must carry `--store mz`. Run commands with
    `uv run harness ...` from the repo root.

    **Your deliverable is `review/PP-NNN/proposal.json`, normalized and clean.
    STOP THERE.**

    Specifically, do:
      - `uv run harness ocr gaps PP-NNN` first. Report what it says.
        gt/fig/chukchi-PP-NNN.xml exists so figures are masked and a band is
        meaningful. If you judge a band to be a genuinely dropped printed line,
        use `harness ocr adopt-gap` per the skill and record it in the proposal's
        `segmenter_missed` block — but that is a real judgement, so say why in
        your final report.
      - Read the full page raster scans/chukchi-PP-NNN.png for orientation.
      - `uv run harness ocr lines PP-NNN --store mz` and `uv run harness ocr
        sheets PP-NNN --store mz`. Read EVERY sheet in full before you zoom at
        anything.
      - Zoom only for specific nameable doubts the sheets left open, selecting all
        lines in ONE call, `--zoom 2` by default. **Never above `--zoom 4`.**
        Use `--margins`.
      - Author review/PP-NNN/proposal.json: one entry per ALTO line index, `text`
        mandatory, `resolved` spelling out codepoints for any line with notation,
        `note` for anything an adjudicator would otherwise rediscover, and a
        `contamination` block.
      - `uv run harness proposal fix PP-NNN`, then re-run it without `--fix` until
        it is silent.
      - `uv run harness corpus normalize --commit --path
        review/PP-NNN/proposal.json`, then the same command without `--commit` —
        it must exit 0.

    **Do NOT** run `harness ocr review --serve`, do NOT run `harness ocr restore`,
    do NOT write into gt/ocr/ (except via `adopt-gap`, which writes geometry
    only), do NOT run `views build` or a bare `corpus normalize`, and do NOT
    commit anything to git. A human adjudicates your proposal afterwards; that
    step is not yours.

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
      - Never take the CATMuS machine text in mz/ocr/ as a witness to any
        non-ASCII glyph — it reads 0% of the transcription inventory. It is
        evidence about line geometry and English only. Your proposal must be YOUR
        reading of the raster, never seeded from the machine text.
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
