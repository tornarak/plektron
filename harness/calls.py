"""What a page's reading actually cost, written by the tool rather than recalled.

Every reader's report in the batch that prompted this understated its own image
ladder, and none of them was lying. `1-039`'s said the folio was "read directly off
the full-page composite, no zoom needed beyond confirming the digit shapes"; its
directory holds five crops of that folio, four margin-widened, two at 4x, one named
for the moment it discovered which line index it had wanted all along. `1-043`'s
said "roughly 14 targeted zoom calls" over a directory of 32.

**The report is written after the answer is known, and by then the search that
produced it no longer feels like a search.** A reason typed at the moment of the
call survives that — which is what `--reason` is for — but a *tally* reconstructed
at the end will keep coming out flattering, because it is a memory of effort and
effort is what gets forgotten once it pays off. So the count cannot come from the
reader. It comes from here.

One line per image-producing call, appended where the page's own working files
live, so `ocr calls` can hand the adjudicator the series rather than the summary:
which lines were opened, at what scale, in what order, and — for a zoom — why. A
page that took forty crops says so in the report a human reads, and a re-aimed
miss is visible as the same line appearing twice with the span nudged.

Gitignored (`review/*/*.jsonl`) and outside `paths.DERIVED`, so it is neither
committed nor swept by `ocr clean` — the images go, the record of having opened
them stays. Append-only: nothing here rewrites a line, because a ledger that can be
edited by the party it measures is not a ledger.
"""
from __future__ import annotations

import json
from pathlib import Path

from .context import norm_ref
from .paths import review_dir


def calls_path(ref: str, root: Path = Path(".")) -> Path:
    return review_dir(ref, root) / "calls.jsonl"


def log_call(ref: str, action: str, root: Path = Path("."),
             reason: str = "", **detail) -> None:
    """Append one call. Silent on any failure — measurement never breaks a pass.

    A ledger that can abort the command it records would make reading a page
    depend on the bookkeeping succeeding, which inverts what this is for.

    **"Any failure" now means any**, which it did not. The catch was `OSError`
    alone, so a `detail` value `json` cannot encode — a `Path`, a `set`, a numpy
    scalar, all of which the call sites have to hand — raised `TypeError` out of
    `json.dumps` and killed the reading this was recording. `default=str` renders
    such a value rather than refusing it, because a ledger entry that says
    `"span": "PosixPath('…')"` is worth more than no entry and much more than a
    dead pass, and the broadened catch is the backstop under that.

    **Zero is a count, and it was being deleted.** The filter read `v not in
    (None, "", False)`, and `0 == False` in Python, so `images=0` and `zoom=0`
    vanished — reading back indistinguishable from a call that never named them.
    This module exists because self-reported counts come out flattering, so
    silently dropping the smallest count there is was the one bias it could not
    afford. Identity for `False`, equality for the rest.
    """
    try:
        p = calls_path(ref, root)
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"action": action,
               **{k: v for k, v in detail.items()
                  if v is not None and v is not False and v != ""}}
        if reason:
            rec["reason"] = reason
        line = json.dumps(rec, ensure_ascii=False, default=str)
        with p.open("a", encoding="utf-8") as fh:
            # **A crashed write costs one record, not two.** An interrupted
            # append leaves a tail with no newline; opening in "a" put the next
            # record on that same line, so the pair became one unparseable line
            # and `read_calls` dropped both. Cheap to prevent, and the case is
            # ordinary here — the pass this records is killed by a reader that
            # ran out of turns.
            if fh.tell() and not _ends_with_newline(p):
                fh.write("\n")
            fh.write(line + "\n")
    except (OSError, TypeError, ValueError):
        pass


def _ends_with_newline(p: Path) -> bool:
    """Whether the ledger's last byte is a newline. Read, not remembered: another
    process may have appended since this one opened the file."""
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            if not fh.tell():
                return True
            fh.seek(-1, 2)
            return fh.read(1) == b"\n"
    except OSError:
        return True


def read_calls(ref: str, root: Path = Path(".")) -> list[dict]:
    """Every logged call for the page, in the order they were made."""
    p = calls_path(ref, root)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def call_summary(ref: str, root: Path = Path(".")) -> dict:
    """The counts an adjudicator reads first: how many images, and how concentrated.

    `repeats` is the number of calls that named a line an earlier call had already
    named — the re-aim signature. It is the one figure here that is not a total,
    because a page's crop count is only alarming next to how many distinct doubts
    it was spent on: seven crops over seven lines is a careful page, seven over two
    is a reader that could not frame what it wanted.
    """
    calls = read_calls(ref, root)
    seen: set[str] = set()
    repeats = 0
    for c in calls:
        for tok in str(c.get("only", "")).replace(" ", "").split(","):
            line = tok.partition("@")[0]
            if not line:
                continue
            if line in seen:
                repeats += 1
            seen.add(line)
    # `.get`, not `[...]`. `read_calls` tolerates a malformed *line* and then
    # this crashed on a well-formed one lacking `action` — a JSON object the
    # reader hands back intact. The tolerance stopped one layer short of being
    # useful, which is the shape of a guard that only half exists.
    zooms = [c for c in calls if c.get("action") == "zoom"]
    return {"ref": norm_ref(ref), "calls": len(calls), "zooms": len(zooms),
            "at_4x": sum(1 for c in zooms if c.get("zoom") == 4),
            "lines_opened": len(seen), "repeats": repeats,
            "no_reason": sum(1 for c in zooms if not c.get("reason"))}
