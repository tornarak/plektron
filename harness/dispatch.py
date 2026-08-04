"""Render the reading pass's subagent prompt from `dispatch.md`, with the survey done.

**The template is not here.** It lives between the `<!-- prompt:begin -->` and
`<!-- prompt:end -->` markers in `.claude/skills/rebuild-groundtruth/dispatch.md`,
which owns the pass's reasoning; this module only substitutes and refuses. Keeping
the prose there is the whole point — a template copied into Python is a second
normative text that drifts from the first, and the drift is invisible because both
look authoritative.

Why it exists at all: the prompt was assembled by hand twice in one session, and the
second time five clauses reached the agent that existed nowhere in the doc. So the
doc described a prompt nobody sent, the run measured something unwritten, and anyone
debugging the outcome afterwards would have been reading the wrong text. That is the
same fault as writing a glyph into a note instead of citing its codepoint — a
normative thing reproduced probabilistically, with nothing to witness the difference
— and it is the reason `tei context` builds the collation prompt rather than asking
a coordinator to assemble one.

**The refusals are the survey made mechanical.** `dispatch.md` tells a coordinator to
check four stores before sending anyone, and the one that matters is `gt/ocr/`: a
page already in the ground-truth store is not a restoration candidate, because every
ALTO verb the agent runs then hands it the keyed human text and its proposal stops
being an independent reading. A named range contains such a page sooner or later —
`2-031`–`2-035` contained `2-034` — and eyeballing four directories is exactly the
check a tired coordinator skips. Here it is a precondition of the prompt existing.
"""

from __future__ import annotations

import re
from pathlib import Path

from .context import norm_ref

DOC = Path(".claude/skills/rebuild-groundtruth/dispatch.md")
BEGIN, END = "<!-- prompt:begin -->", "<!-- prompt:end -->"

# The figure clause is a whole sentence rather than a word, because the two cases
# say opposite things about what a `gaps` band means and an agent told the wrong one
# will either read artwork as a dropped line or discount a real one as artwork.
FIGURES_PRESENT = (
    "gt/fig/chukchi-{ref}.xml exists, so the figures are masked out of the "
    "detector and a band it reports is meaningful rather than artwork.")
FIGURES_ABSENT = (
    "gt/fig/chukchi-{ref}.xml does NOT exist, and the figure track is complete "
    "at 252 pages, so this page has no figures: nothing is being masked and "
    "**every band it reports is a genuine dropped-line candidate**, not "
    "something to discount as a photograph.")


class Unready(Exception):
    """The page is not a dispatch candidate, and the message says what to do."""


def template(root: Path = Path(".")) -> str:
    """The prompt block from `dispatch.md`, dedented, markers stripped."""
    doc = root / DOC
    if not doc.exists():
        raise Unready(f"{DOC} is missing; it is the prompt's only source")
    text = doc.read_text(encoding="utf-8")
    try:
        body = text.split(BEGIN, 1)[1].split(END, 1)[0]
    except IndexError:
        raise Unready(
            f"{DOC} has no {BEGIN} / {END} pair; the template is delimited by "
            "them and cannot be located by heading alone") from None
    lines = [ln[4:] if ln.startswith("    ") else ln
             for ln in body.strip("\n").splitlines()]
    return "\n".join(lines).strip("\n")


def survey(ref: str, root: Path = Path(".")) -> dict:
    """What the four stores hold for this page — the check `dispatch.md` describes."""
    from .lines import alto_for_lines, page_lines
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
    text = template(root).format(
        ref=r, root=str(root.resolve()), lines=s["lines"], zones=s["blocks"],
        figures=figs, note=f" {note.strip()}" if note else "")
    left = sorted(set(re.findall(r"\{(\w+)\}", template(root))))
    return {**s, "prompt": text, "placeholders": " ".join(left)}
