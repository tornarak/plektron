"""Deal a batch of pages out to readers, one each, without naming one in a prompt.

**Two texts, and the split between them is the whole design.** `queue` prints the
prompt every reader gets, and it is the same 70-odd characters for every reader of
this book — no ref, no substitution, fixed across batches so next month's readers
share a cached prefix with tonight's. `claim` prints the page block: the ref, and
what the survey found about it. The reader runs `claim` itself, so what varies
between siblings arrives from a tool result rather than from the words they were
sent.

**Why, measured on the sibling pass over Moll.** Three readers dispatched with
`moll-043`/`044`/`045` in their prompts all opened COLD, at the same total to the
token — the totals matching because three refs of the same byte length cost the
same. A batch whose prompts were byte-identical shared. So the first user turn is
folded into the cached block, and **identity of turn 1 is what caches, not its
position or its size**: a per-page prompt costs every reader the entire shared
prefix, however small the varying part is. The consequence is general — anything
that differs between siblings must arrive from a tool call.

**Neither template is here.** Both live between markers in
`.claude/skills/rebuild-groundtruth/dispatch.md`, which owns the pass's reasoning;
this module only substitutes and refuses. A template copied into Python is a second
normative text that drifts from the first, and the drift is invisible because both
look authoritative. The prompt was assembled by hand twice in one session, and the
second time five clauses reached the agent that existed nowhere in the doc — the doc
then described a prompt nobody sent. Same fault as writing a glyph into a note
instead of citing its codepoint.

**The refusals are the survey made mechanical**, and they fire at `queue` time —
while the fix is still a command, rather than in front of an agent with no way to
act on it. `dispatch.md` tells a coordinator to check four stores before sending
anyone, and the one that matters is `gt/ocr/`: a page already in the ground-truth
store is not a restoration candidate, because every ALTO verb the agent runs then
hands it the keyed human text and its proposal stops being an independent reading.
A named range contains such a page sooner or later — `2-031`–`2-035` contained
`2-034` — and eyeballing four directories is exactly the check a tired coordinator
skips.

**A claim is never released.** A reader that dies holding one leaves its page unread
and its claim standing, which is the honest state rather than a silent retry:
`reconcile` names the ref and re-queueing it is a decision somebody makes.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from .context import norm_ref
from .lines import ZOOM

DOC = Path(".claude/skills/rebuild-groundtruth/dispatch.md")
# The page block, rendered by `claim` — everything true of one page in particular.
BEGIN, END = "<!-- prompt:begin -->", "<!-- prompt:end -->"
# The prompt itself, printed by `queue` and sent to every reader unedited.
CLAIM_BEGIN, CLAIM_END = "<!-- claim:begin -->", "<!-- claim:end -->"

# The batch, and the claims already taken off it. Both live beside the page
# directories they deal out, which is why `paths.page_dirs` exists: `review/` is now
# a tree with a child that is not a page.
QUEUE = Path("review/_queue.txt")
CLAIMS = Path("review/_claims")

# The figure clause is a whole sentence rather than a word, because the two cases
# say opposite things about what a `gaps` band means and an agent told the wrong one
# will either read artwork as a dropped line or discount a real one as artwork.
FIGURES_PRESENT = (
    "gt/fig/chukchi-{ref}.xml exists, so the figures are masked out of the "
    "detector and a band it reports is meaningful rather than artwork. **You "
    "will see them on the page image as grey blocks reading BLOTTED FIGURE / DO "
    "NOT TRANSCRIBE**, and the vertical jump between the line indices either "
    "side of one is that figure, not a dropped line: it is already adjudicated "
    "in the figure track and is nobody's to key. Do not spend an image on it.")
FIGURES_ABSENT = (
    "gt/fig/chukchi-{ref}.xml does NOT exist, and the figure track is complete "
    "at 252 pages, so this page has no figures: nothing is being masked and "
    "**every band it reports is a genuine dropped-line candidate**, not "
    "something to discount as a photograph.")


class Unready(Exception):
    """The page is not a dispatch candidate, and the message says what to do."""


def template(root: Path = Path("."), markers: tuple[str, str] = (BEGIN, END)) -> str:
    """One delimited block from `dispatch.md`, dedented, markers stripped.

    **A marker counts only on a line of its own.** The doc explains its own
    delimiters, so a substring search finds the sentence describing a template
    before the template — which, the first time a second marker pair was added,
    printed that paragraph to a coordinator as though it were instructions.
    """
    begin, end = markers
    doc = root / DOC
    if not doc.exists():
        raise Unready(f"{DOC} is missing; it is the prompt's only source")
    lines = doc.read_text(encoding="utf-8").splitlines()
    try:
        i = lines.index(begin)
        j = lines.index(end, i)
    except ValueError:
        raise Unready(
            f"{DOC} has no {begin} / {end} pair on lines of their own; the "
            "template is delimited by them and cannot be located by heading "
            "alone") from None
    body = "\n".join(lines[i + 1:j])
    return "\n".join(ln[4:] if ln.startswith("    ") else ln
                     for ln in body.strip("\n").splitlines()).strip("\n")


def survey(ref: str, root: Path = Path(".")) -> dict:
    """What the four stores hold for this page — the check `dispatch.md` describes."""
    from .lines import alto_for_lines, page_lines, zoom_capacity
    ref = norm_ref(ref)
    exempt = root / "gt/zones/_exempt.lst"
    out = {
        "ref": ref,
        "zones": (root / "gt/zones" / f"chukchi-{ref}.xml").exists(),
        # A human ruled this "not a text page" — a plate, map, foldout or blank.
        # Distinct from "keyed and holds nothing", which is the distinction the
        # zone store exists to keep, and the reason a dispatch can trust it.
        "exempt": (exempt.exists()
                   and f"chukchi-{ref}.xml" in exempt.read_text(
                       encoding="utf-8").split()),
        "figures": (root / "gt/fig" / f"chukchi-{ref}.xml").exists(),
        "gt": (root / "gt/ocr" / f"chukchi-{ref}.xml").exists(),
        "mz": (root / "mz/ocr" / f"chukchi-{ref}.xml").exists(),
        "lines": 0,
        "blocks": 0,
    }
    if out["mz"]:
        alto = alto_for_lines(ref, "mz/ocr", root)
        recs = page_lines(alto, root)
        out["lines"] = len(recs)
        out["blocks"] = len({r["block_id"] for r in recs if r.get("block_id")})
        # **The zoom geometry belongs here, before the first image, not on the
        # call that renders one.** `ocr zoom` has printed this table since the
        # step was restricted, and printing it there is too late: by the time a
        # reader sees what a crop covers it has already chosen a line, a
        # magnification and a span, and the numbers arrive as a comment on a
        # decision rather than an input to one. Three readers in the 1-045..047
        # batch read the table on every call and went on re-aiming — one walked a
        # word across three 4x crops, having escalated before asking whether the
        # word would fit in a strip at that step.
        #
        # Measured off this page's own lines, so it is this page's arithmetic and
        # not a rule of thumb: a reader that knows a 4x crop shows a fifth of a
        # line knows, before it starts, that a whole word wants 2x.
        out["zoom"] = zoom_capacity([r["width"] for r in recs],
                                    [r["height"] for r in recs])
    return out


def build(ref: str, root: Path = Path("."), note: str | None = None) -> dict:
    """The prompt for one page, or `Unready` naming the command that fixes it.

    Refuses rather than warns, and each refusal names its remedy. A prompt is a
    thing somebody is about to spend an agent on; "probably fine" is not a state it
    should be possible to dispatch from.
    """
    s = survey(ref, root)
    r = s["ref"]
    if not s["zones"]:
        raise Unready(
            f"{r}: no gt/zones/chukchi-{r}.xml — not a keyed text page, so there "
            "is nothing for `ocr predict` to have segmented. No zones, no dispatch.")
    if s["exempt"]:
        raise Unready(
            f"{r}: marked exempt in gt/zones/_exempt.lst — a human ruled it not a "
            "text page (a plate, map, foldout or blank). There is nothing to read, "
            "and the ruling is a statement rather than an absence, so this is a "
            "refusal and not a warning.")
    if s["gt"]:
        raise Unready(
            f"{r}: gt/ocr/chukchi-{r}.xml already exists, so this is a *revision*, "
            "not a restoration. A reader sent at it reads the keyed human text "
            "through every ALTO verb, and its proposal stops being an independent "
            "witness. Substitute a page with zones and no gt, and say in the "
            "report that you did and why.")
    if not s["mz"]:
        raise Unready(
            f"{r}: nothing in mz/ocr/ — an agent sent at it has no line indices to "
            f"key against and will stall or invent a numbering. Run "
            f"`uv run harness ocr predict {r}` first, in the parent: it wants the "
            "GPU, and several agents racing for it is slower than one loop.")
    figs = (FIGURES_PRESENT if s["figures"] else FIGURES_ABSENT).format(ref=r)
    # Rendered as sentences, not as the table `ocr zoom` prints. The reader is
    # being handed this before it has a doubt to spend it on, so what it has to
    # carry is the consequence — "a whole line is N strips" — rather than a row of
    # figures it would have to do arithmetic on later, at the moment it is least
    # inclined to.
    zoom = "\n".join(
        f"  - at {c['zoom']}x one crop shows ~{c['covers_pct']}% of a line "
        f"however you aim it, {c['points_per_sheet']} fit one sheet, and a whole "
        f"line is {c['full_strips']} strips — "
        + ("so a whole word fits; this is the step to look at."
           if c["zoom"] == ZOOM else
           "so a long word does NOT fit and comes back in pieces. One mark only.")
        for c in s.get("zoom") or [])
    text = template(root).format(
        ref=r, lines=s["lines"], zones=s["blocks"], zoom=zoom,
        figures=figs, note=f" {note.strip()}" if note else "")
    left = sorted(set(re.findall(r"\{(\w+)\}", template(root))))
    return {**s, "page_block": text, "placeholders": " ".join(left)}


AGENT = Path(".claude/agents/groundtruth-reader.md")
TRANSCLUDE = re.compile(
    r"^<!-- transclude: (?P<src>\S+) -->$.*?^<!-- /transclude -->$",
    re.MULTILINE | re.DOTALL)


def sync_transcludes(root: Path = Path("."), agent: Path = AGENT) -> dict:
    """Refill the agent's transcluded blocks from the files they name.

    **The reader's whole contract has to be in its system prompt, and
    `keying_spec.md` has to stay one file.** Those pull opposite ways. The spec
    binds the collation pass and the human keying track as well, so it cannot
    move into an agent definition; but a `Read` of it costs ~15k tokens per
    reader per page, behind the turn that varies, where nothing can share it.

    So it is copied in, and the copy is mechanical: this rewrites each marked
    block from its source on every `queue`, and `test_transclusion.py` fails if
    the checked-in file and its source disagree. Two copies with a gate between
    them is what this repo already does for `VERBS.md` and the CLI tree — what it
    forbids is two copies with a *comment* between them.

    Returns the sources that changed, so `queue` can say so: the agent file is
    tracked, and a changed block is a commit somebody makes.
    """
    p = root / agent
    if not p.exists():
        return {"agent": str(agent), "updated": []}
    text = p.read_text(encoding="utf-8")
    updated = []

    def swap(m: re.Match) -> str:
        src = m.group("src")
        f = root / src
        if not f.exists():
            raise Unready(
                f"{agent} transcludes {src}, which does not exist. The block is "
                "a copy under a gate, so a missing source is a contract with a "
                "hole in it rather than a stale copy to leave alone.")
        body = f.read_text(encoding="utf-8").strip("\n")
        if body != m.group(0).split("\n", 1)[1].rsplit("\n", 1)[0].strip("\n"):
            updated.append(src)
        return (f"<!-- transclude: {src} -->\n{body}\n<!-- /transclude -->")

    new = TRANSCLUDE.sub(swap, text)
    if new != text:
        p.write_text(new, encoding="utf-8")
    return {"agent": str(agent), "updated": updated}


def queue_path(root: Path = Path(".")) -> Path:
    return root / QUEUE


def claims_dir(root: Path = Path(".")) -> Path:
    return root / CLAIMS


def queue_refs(refs: list[str], root: Path = Path("."),
               note: str | None = None) -> dict:
    """Validate a batch, write it to the queue, and return the one fixed prompt.

    Every page is checked before any is queued, and the page block is rendered and
    thrown away — a page whose survey raises fails here, where the fix is a command,
    rather than in front of a reader that cannot act on it.

    **A ref named twice is one page and two readers**, which is not a valid batch:
    they overwrite each other's proposal and the run comes back a page short with
    nothing able to say which page went missing. The refs go on the queue in the
    order they were named.
    """
    seen, ordered = set(), []
    for ref in refs:
        r = norm_ref(ref)
        if r in seen:
            raise Unready(
                f"{r} is named twice. A ref appears once per batch: two readers "
                "on one page overwrite each other, and the batch is a page short "
                "with nothing able to say which one.")
        seen.add(r)
        ordered.append(r)
    for r in ordered:
        build(r, root, note)
    q, c = queue_path(root), claims_dir(root)
    q.parent.mkdir(parents=True, exist_ok=True)
    # **The claims are cleared with the queue, never separately.** A claim standing
    # against a new batch would silently withhold a page from it — the reader that
    # would have taken it moves on to the next ref, and the batch comes back short
    # for a reason that is a file from last week.
    if c.exists():
        for f in c.iterdir():
            f.unlink()
    body = "".join(f"{r}\t{note.strip()}\n" if note else f"{r}\n" for r in ordered)
    q.write_text(body, encoding="utf-8")
    # Last, so a batch that was going to be refused does not also rewrite a
    # tracked file on its way out.
    synced = sync_transcludes(root)
    return {"queued": ordered, "prompt": template(root, (CLAIM_BEGIN, CLAIM_END)),
            "resynced": synced["updated"]}


def claim_one(root: Path = Path(".")) -> tuple[str, str] | None:
    """Take the next unclaimed ref off the queue, atomically, or None.

    **`O_CREAT|O_EXCL` is the whole mechanism.** The file system decides which of
    several readers created the marker first, so two agents racing for one ref
    cannot both win — there is no window between the check and the take that an
    `if not exists: write` would leave open. Readers are dispatched simultaneously
    and by design cannot see each other, so a lock resting on politeness rests on
    nothing.

    The queue file is never rewritten; a claim is a marker beside it. Returns
    `(ref, note)`, the note being whatever the batch was queued with.
    """
    q, c = queue_path(root), claims_dir(root)
    if not q.exists():
        return None
    c.mkdir(parents=True, exist_ok=True)
    for line in q.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ref, _, note = line.partition("\t")
        ref = ref.strip()
        try:
            fd = os.open(c / ref, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        # Stamped for diagnosis only — nothing reads it to decide anything. A batch
        # of twenty that comes back one page short is a question about *which*
        # reader stalled, and a bare marker cannot answer it.
        os.write(fd, f"{datetime.now().astimezone().isoformat()}\n".encode())
        os.close(fd)
        return ref, note.strip()
    return None


def claim(root: Path = Path(".")) -> dict | None:
    """`claim_one`, then the page block for whatever it took. None if the queue is out."""
    taken = claim_one(root)
    if taken is None:
        return None
    ref, note = taken
    return build(ref, root, note or None)


def reconcile(refs: list[str], root: Path = Path(".")) -> list[dict]:
    """Each ref as keyed / claimed-no-proposal / unclaimed.

    **Three states rather than two**, because "no proposal" has two very different
    causes at scale and they want different answers: nobody took the page (the queue
    outran the readers, or they were never sent), or somebody took it and did not
    come back (died, or ran out of turns). Only the second is worth chasing.
    """
    from .paths import proposal_path
    c = claims_dir(root)
    out = []
    for ref in refs:
        r = norm_ref(ref)
        marker = c / r
        when = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
        if proposal_path(r, root).exists():
            state = "keyed"
        elif marker.exists():
            state = "CLAIMED, no proposal"
        else:
            state = "unclaimed"
        out.append({"ref": r, "state": state, "claimed_at": when})
    return out
