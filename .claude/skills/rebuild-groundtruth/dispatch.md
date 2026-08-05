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

**One ref per agent, and nobody hands it over.** Several agents in one repo are
safe only because they touch disjoint `review/PP-NNN/` directories, and what keeps
them disjoint is `claim`: it takes the next ref off `review/_queue.txt` with
`O_CREAT|O_EXCL`, so the file system decides who got it and there is no window
between the check and the take. Eight concurrent claimers over a three-ref queue
return three distinct refs.

### Why the prompt names no page

A reader's context has exactly one block its siblings can share: the system prompt
— agent body, tool schemas, `CLAUDE.md`, memory index — which is the only part
ahead of every user turn. Everything behind the first differing byte is written per
reader.

Two things were on the wrong side of that line, and both are now fixed.

**The preloaded `skills:` doc arrived as a message**, behind the turn naming the
page, so ~40k characters of invariant text sat behind the one thing that varied and
every reader wrote it in full. Moving it into the agent body — which *is* the system
prompt — cut the sibling pass's fixed overhead for three readers from ~118k tokens
to ~50k. A `standby` handshake that delivered the ref on resume also worked, but
**resume re-injects a preloaded skill whole**: request 2 cost 14,916 tokens for
three readers identically and separately, giving half the saving straight back.

**Then the ref itself.** Three readers dispatched with `moll-043`/`044`/`045` in
their prompts all opened **COLD**, at the same total to the token — the totals
matching because three refs of the same byte length cost the same. A batch whose
prompts were byte-identical shared. So the first user turn is folded into the cached
block: **identity of turn 1 is what caches, not its position or its size**, and a
per-page prompt costs every sibling the entire prefix however few characters vary.
`queue`/`claim` gets that property with no handshake and so no re-injection.

The same batch measured here: six readers over `1-031`..`1-036`, every one COLD at
36,856 tokens — six copies of one context. `harness agents usage` reports this as a
cohort with no warm members, and it is the check to run after any batch.

**Stagger the first launch about ten seconds, then fan out the rest together.** One
member of a cohort has to write the prefix and the others read it, so a sibling that
opens before that write completes writes its own. An earlier measurement — a reader
launched twelve seconds after another opening within 1% of one launched
simultaneously — is *not* evidence against this: it was taken when the prompts
differed, so no sharing was possible either way. `agents usage` reports what the
stagger bought as `missed`, so it is checkable after the fact rather than assumed;
if `missed` is 0 on a fanned-out batch, drop it.

The saving is small against a large allowance, and that is not the reason. This pass
is meant to be runnable by people on cheaper plans and other platforms, where the
same fixed prefix is paid at every scale. Note also that the agent's memory index
sits in its system prompt: when a reader adds to
`.claude/agent-memory/groundtruth-reader/`, the prefix changes and the next batch
pays a full write. That is the cost of the memory channel, not a fault in it — and
it is once per batch, not once per reader.

## What the two texts have to carry, and why each clause is there

Every item below was earned by something going wrong, in this project or in the
dispatch that produced this file.

**Almost all of it lives in `.claude/agents/groundtruth-reader.md`**, and the split
is by what varies: the agent body carries everything true of *every* page — the loop,
the ladder, the proposal contract, the hard rules, the report shape, and the reading
checklist and `keying_spec.md` transcluded whole — while the claim-rendered block
carries only the ref, the survey and the figures clause. Three things follow. A
clause edited in the agent file reaches the next reader with no rendering step; the
page block is a dozen lines instead of 210, so what is page-specific is legible as
such; and none of the standing text is written per reader, because all of it is
ahead of the first varying byte.

**The spec is transcluded, not read.** `keying_spec.md` cannot move here — it binds
the collation pass and the human keying track too — but a `Read` of it costs ~15k
tokens per reader per page, behind the varying turn, where nothing can share it. So
the agent file carries a copy between markers, `harness ocr queue` re-syncs it from
the source before every batch, and `test_transclusion.py` fails if the committed
copy and the source disagree. Two copies with a gate between them, which is what
this repo already does for `VERBS.md` and the CLI tree; what it forbids is two
copies with a comment between them.

What the split costs is a new way to be wrong, and it is the failure mode this repo
has paid for twice: **a reader dispatched under the wrong agent type gets none of
it, and nothing would look amiss.** Same shape as a file whose role lived only in
the directory holding it. So the *fixed prompt* — not the agent body — carries the
assertion and tells the reader to stop if it does not have the contract. It has to
live there: an agent spawned as the wrong type does not have the body, so an
assertion inside it could never catch the case it exists for.

- **Claim the page, do not choose one.** "Run it once" is explicit, because a second
  claim takes a page off the queue that this reader will not read, and the batch
  comes back short with nothing able to say why.
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
  there is no source detail left to buy.
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
| one `sheets … 10-14` | 1904×517 | 1.00× | ~1,300 |
| one `zoom2` sheet | 1450×1460 | 1.00× | ~2,760 |

Two things follow, and the first is not obvious. **A whole page cannot be delivered
above about 0.64× however many pixels you send** — the ceiling does the downscaling
— so the numbered composite is a fixed ~4.8k tokens and can never settle a question
about one mark. It is an orientation instrument. But `2-031`'s three contact sheets
cost ~14.3k for the same page, and the prompt used to make reading all of them
mandatory before any zoom. Most pages of this book are English prose that never
needs a crop.

So: **`numbered` → `sheets LINES` → `zoom PLACES`**, each rung paid for only where
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

## The two templates

**Do not transcribe either by hand — `harness ocr queue` and `harness ocr claim`
render them.** The blocks below are the source and this section is their reasoning;
the verbs substitute, and are the only things that should ever produce a prompt.

That rule was written after being broken twice in one session. Hand-copying put
five clauses into the prompt an agent actually ran that existed nowhere in this
file — so the doc described a prompt nobody sent, the run measured something
unwritten, and anyone debugging the result afterwards would have debugged the wrong
text. It is the same fault as writing a glyph into a note instead of citing its
codepoint: a normative thing reproduced probabilistically, with no witness to the
difference.

The markers are load-bearing (`harness/dispatch.py` reads between them) and count
only on a line of their own — this file describes its own delimiters, so a
substring search finds the sentence before the template. The `{braces}` are
substituted; everything else is sent verbatim, so prose edited here reaches the
next agent with no other step.

### The prompt every reader gets

**Spawn every reader with `subagent_type: groundtruth-reader` and this text,
unedited and identical.** It names no page, carries no `{braces}`, and is fixed
across batches as well as within one, so next month's readers share a cached prefix
with tonight's. Identity is the whole property being bought: a ref in turn 1 costs
every sibling the entire shared context, however few characters it is.

The wrong-agent clause stays here and stays out of the agent body, because a reader
dispatched as the wrong type does not *have* the body — an assertion living there
could never catch the case it exists for. It costs nothing, carrying no ref.

<!-- claim:begin -->

    Claim a page. If you have no groundtruth-reader contract, stop and say so.

<!-- claim:end -->

### The page block `claim` prints

Everything true of one page in particular, and nothing else. What used to sit here
as well — the deliverable, the STOP, the report instruction, the standing-instructions
paragraph — is standing text and lives in `.claude/agents/groundtruth-reader.md`.
Of two copies of a rule, the one in a rendered prompt is the one that drifts, and it
was restating the ref four times over to say things derivable from it.

<!-- prompt:begin -->

    Your page ref is **{ref}**. Do not touch any other page, and do not claim a
    second: one reader, one page.

    What the survey found:
      - `mz/ocr/chukchi-{ref}.xml` exists — {lines} lines over {zones} zones.
        `harness ocr predict` has been run for you, in the parent.
      - `gt/ocr/chukchi-{ref}.xml` does not exist.{note}
      - So this is a **restoration**, and every ALTO verb you run carries
        `--store mz`.
      - {figures}

    What a crop of THIS page will show you, measured off its own lines — read it
    now, before you form any intention to zoom:
    {zoom}

    So: name points, not ranges. A point is one number and the renderer widens and
    snaps it for you; a range is two numbers about a word whose extent you cannot
    see from a composite, and the second one is the one that goes wrong. `@0` and
    `@100` are the head and tail of a line exactly, whatever its length, so a
    footnote opener is `N@0` and a trailing reference `N@100` — neither asks you
    to estimate. Every crop also runs well past its line's box, so a folio whose
    box strangles it still comes back whole: read it off the composite or a sheet
    and spend nothing on it.

<!-- prompt:end -->
